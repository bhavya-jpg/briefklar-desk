"""Pipeline in replay mode (spec 17.4) plus unit tests of the deterministic parts around the model."""

import json
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from briefklar.i18n import DUE_DATE_TOKEN
from briefklar.llm.client import LLMClient, ReplayMiss, Response, ToolCall
from briefklar.models import (
    Case, DeadlineResult, Explanation, Letter, LetterFacts, Money, Page, RedFlag, Sentence, Thread, Verification,
)
from briefklar.pipeline import case as case_pass
from briefklar.pipeline import check, explain, verify

DATA = Path(__file__).parent / "data"
PROJECT = Path(__file__).resolve().parent.parent
EXPECTED = DATA / "demo_case_expected.json"


def normalised(case: dict) -> dict:
    """The case without what legitimately differs between runs: the random case id and the clock."""
    text = json.dumps(case, ensure_ascii=False, sort_keys=True).replace(case["id"], "CASE")
    data = json.loads(text)
    data.pop("created_at")
    return data


# -- golden test ---------------------------------------------------------------------------------


def test_demo_case_matches_golden(demo_case):
    actual = normalised(demo_case)
    if os.environ.get("BRIEFKLAR_UPDATE_GOLDEN") == "1":
        EXPECTED.write_text(json.dumps(actual, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    assert EXPECTED.is_file(), "run once with BRIEFKLAR_UPDATE_GOLDEN=1 to create the golden file"
    assert actual == json.loads(EXPECTED.read_text(encoding="utf-8"))


def test_demo_case_headline_facts(demo_case):
    by_label = {l["label"]: l for l in demo_case["letters"]}
    order = [next(l["label"] for l in demo_case["letters"] if l["id"] == i) for i in demo_case["order"]]
    assert order[0] == "demo-04", "the letter with warning signs comes first"
    assert order[1:4] == ["demo-03", "demo-02", "demo-01"], "the payment order leads its thread"
    payment_order = by_label["demo-03"]
    deadline = payment_order["verification"]["deadline"]
    assert (deadline["due_date"], deadline["days_left"], deadline["verified_rule"]) == ("2026-10-19", 9, True)
    assert payment_order["amount_display"] == "CHF 1’240.00"
    flags = {f["code"] for f in by_label["demo-04"]["verification"]["red_flags"]}
    assert flags == {"CONTACT_MISMATCH", "FOREIGN_IBAN_FOR_AUTHORITY", "LEGAL_BASIS_INCONSISTENT"}
    assert by_label["demo-04"]["reply_templates"] == [], "no reply is offered for a letter with warning signs"
    thread = demo_case["threads"][0]
    assert thread["confirmed"] and len(thread["letter_ids"]) == 3
    totals = {t["creditor"]: t["total"] for t in demo_case["creditor_totals"]}
    assert totals["Alpenblick Versand AG"] == "1240.00", "a matter counts once, at its latest letter"
    assert all(l["status"] == "done" for l in demo_case["letters"])


def test_every_explanation_sentence_is_grounded(demo_case):
    for letter in demo_case["letters"]:
        valid = {e["id"] for e in letter["facts"]["evidence_items"]} | {"flags"}
        for key in ("explanation", "explanation_de"):
            for section in ("what_this_is", "what_they_want", "deadline", "what_you_can_do", "who_to_contact"):
                sentences = letter[key][section]
                assert sentences, f"{letter['label']} {key}.{section} is empty"
                for sentence in sentences:
                    assert sentence["support"], sentence
                    assert all(s in valid or s.startswith("card:") for s in sentence["support"])
                    assert DUE_DATE_TOKEN not in sentence["text"], "the date token must be replaced before display"


def test_printouts(client, demo_case):
    case_id = demo_case["id"]
    for name in ("handout.pdf", "case-note.pdf"):
        response = client.get(f"/api/cases/{case_id}/{name}")
        assert response.status_code == 200 and response.content[:5] == b"%PDF-"
    html = client.get(f"/api/cases/{case_id}/handout.html").text
    assert 'dir="ltr"' in html and "Letrat tuaja" in html and "http" not in html.replace("http-equiv", "")
    note = client.get(f"/api/cases/{case_id}/case-note.pdf").content
    assert b"Krasniqi" not in note, "the case note carries no client name unless it was typed in"


def test_objection_reply_flow(client, demo_case):
    letter_id = next(l["id"] for l in demo_case["letters"] if l["label"] == "demo-03")
    reply = client.post(f"/api/letters/{letter_id}/replies", json={"template_id": "objection_payment_order"}).json()["reply"]
    assert reply["missing"] == ["place"]
    assert "erhebe ich Rechtsvorschlag" in reply["rendered_text"]
    assert reply["slots"]["enforcement_number"] in reply["rendered_text"]
    assert reply["slot_sources"]["enforcement_number"], "every filled slot keeps its source span"
    edited = client.put(f"/api/replies/{reply['id']}", json={"slots": {"place": "Bern", "objection_sentence": "x"}}).json()["reply"]
    assert edited["missing"] == [] and "Bern, 10.10.2026" in edited["rendered_text"]
    assert "erhebe ich Rechtsvorschlag" in edited["rendered_text"], "fixed wording cannot be edited"
    assert client.get(f"/api/replies/{reply['id']}.pdf").content[:5] == b"%PDF-"
    flagged = next(l["id"] for l in demo_case["letters"] if l["label"] == "demo-04")
    assert client.post(f"/api/letters/{flagged}/replies", json={"template_id": "extension_request"}).status_code == 409


def test_wipe_removes_images_and_results(client):
    case_id = client.post("/api/demo", json={"client_language": "de"}).json()["case_id"]
    store = client.app.state.store
    directory = store.sessions[case_id].dir
    assert any(directory.iterdir())
    assert client.delete(f"/api/cases/{case_id}").json() == {"wiped": True}
    assert not directory.exists()
    assert client.get(f"/api/cases/{case_id}").status_code == 404


def test_idle_cases_are_wiped_after_the_ttl(client):
    case_id = client.post("/api/demo", json={"client_language": "de"}).json()["case_id"]
    store = client.app.state.store
    store.sessions[case_id].last_active -= store.settings.session_ttl_min * 60 + 1
    assert case_id in store.sweep()
    assert case_id not in store.sessions


def test_health_says_replay_and_names_fixtures(client):
    health = client.get("/api/health").json()
    assert health["mode"] == "replay" and health["offline"] is True and health["endpoint_host"] is None
    assert health["replay"]["backend"] in {"fixture", "http"}
    assert len(client.get("/api/languages").json()["languages"]) == 13


# -- schema test ---------------------------------------------------------------------------------


def test_every_cached_extract_output_validates():
    records = [json.loads(p.read_text(encoding="utf-8")) for p in (PROJECT / "data" / "replay").glob("*.json")
               if p.name != "MANIFEST.json"]
    extracts = [r for r in records if r["pass"] == "extract"]
    assert extracts, "data/replay holds no Pass 1 outputs"
    for record in extracts:
        LetterFacts.model_validate_json(record["response"]["content"])


def test_replay_miss_names_the_letter(client):
    with pytest.raises(ReplayMiss, match="demo letter 7.*live"):
        LLMClient(client.app.state.settings).chat([{"role": "user", "content": "never recorded"}],
                                                  pass_name="extract", label="demo letter 7")


# -- deterministic parts around the model --------------------------------------------------------


def make_letter(letter_id: str, letter_type: str = "reminder", **facts) -> Letter:
    base = dict(letter_type=letter_type, source_language="de", sender_name="Alpenblick Versand AG",
                letter_date=date(2026, 9, 1), amount_due=Money(amount=Decimal("100.00")))
    return Letter(id=letter_id, page_ids=[], status="done", facts=LetterFacts(**{**base, **facts}),
                  verification=Verification())


def due(days: int | None, needs: bool = False) -> DeadlineResult:
    when = date(2026, 10, 10 + days) if days is not None else None
    return DeadlineResult(due_date=when, days_left=days, needs_delivery_date=needs, rule_family="contract",
                          trace=["t"], verified_rule=True)


def test_linker_conditions():
    a = make_letter("a", reference_numbers=["2026-123-45"])
    assert "reference" in case_pass.link_reason(a, make_letter("b", reference_numbers=["2026 123 45"], sender_name="X"))
    assert "IBAN" in case_pass.link_reason(make_letter("a", iban="CH93 0076 2011 6238 5295 7"),
                                           make_letter("b", iban="CH9300762011623852957", sender_name="Y"))
    assert "same sender" in case_pass.link_reason(make_letter("a"), make_letter("b", amount_due=Money(amount=Decimal("115.00"))))
    assert case_pass.link_reason(make_letter("a"), make_letter("b", amount_due=Money(amount=Decimal("130.00")))) is None
    order = make_letter("p", "payment_order", sender_name="Betreibungsamt", creditor_name="Alpenblick Versand AG",
                        reference_numbers=["26123456"], amount_due=Money(amount=Decimal("900.00")))
    assert "payment order" in case_pass.link_reason(order, make_letter("r", reference_numbers=["2026-123-45"]))
    assert case_pass.link_reason(make_letter("a"), make_letter("b", sender_name="Other AG")) is None


def test_contradicting_references_veto_fuzzy_links():
    """Two invoices from one creditor are two matters, even with similar amounts."""
    first = make_letter("a", reference_numbers=["2026-111-11"])
    second = make_letter("b", reference_numbers=["2026-222-22"], amount_due=Money(amount=Decimal("105.00")))
    assert case_pass.link_reason(first, second) is None
    order = make_letter("p", "payment_order", sender_name="Betreibungsamt", creditor_name="Alpenblick Versand AG",
                        reference_numbers=["26123456", "2026-111-11"])
    assert case_pass.link_reason(order, second) is None
    assert case_pass.link_reason(order, first) is not None


def test_model_proposals_need_the_linker():
    a, b, c = make_letter("a", reference_numbers=["R-10001"]), make_letter("b", reference_numbers=["R-10001"]), \
        make_letter("c", sender_name="Other AG")
    proposal = case_pass.CaseProposal(threads=[case_pass.ProposedThread(letter_ids=["a", "c"], reason="looks related")])
    threads, misses = case_pass.build_threads([a, b, c], proposal)
    confirmed = [t for t in threads if t.confirmed]
    dashed = [t for t in threads if not t.confirmed]
    assert [t.letter_ids for t in confirmed] == [["a", "b"]] and confirmed[0].origin == "linker" and misses == 1
    assert [t.letter_ids for t in dashed] == [["a", "c"]] and dashed[0].origin == "model"


def test_order_is_flags_then_days_then_date_needed_then_none():
    letters = [make_letter("none"), make_letter("needs"), make_letter("soon"), make_letter("later"), make_letter("flag")]
    letters[1].verification.deadline = due(None, needs=True)
    letters[2].verification.deadline = due(3)
    letters[3].verification.deadline = due(12)
    letters[4].verification.deadline = due(15)
    letters[4].verification.red_flags = [RedFlag(code="X", severity="high", evidence="e")]
    case = Case(id="c", created_at="2026-10-10T00:00:00Z", client_language="de", canton="BE", letters=letters)
    assert case_pass.order_letters(case) == ["flag", "soon", "later", "needs", "none"]


def test_thread_is_ranked_by_its_latest_letter():
    old = make_letter("old", letter_date=date(2026, 9, 1))
    old.verification.deadline = due(-9)  # long overdue reminder
    head = make_letter("head", "payment_order", letter_date=date(2026, 10, 6))
    head.verification.deadline = due(9)
    other = make_letter("other", sender_name="Serafe AG")
    other.verification.deadline = due(5)
    case = Case(id="c", created_at="2026-10-10T00:00:00Z", client_language="de", canton="BE", letters=[old, head, other],
                threads=[Thread(id="t1", letter_ids=["old", "head"], reason="r", confirmed=True)])
    assert case_pass.order_letters(case) == ["other", "head", "old"]


class ScriptedClient(LLMClient):
    """A client whose answers are given by the test."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.stats = {"schema_retries": 0}

    def chat(self, messages, **kwargs):
        answer = self.answers.pop(0)
        return answer if isinstance(answer, Response) else Response(content=answer)


def test_orchestrator_calls_required_tools_the_model_skipped():
    letter = make_letter("x", "payment_order", sender_name="Betreibungsamt Bern-Mittelland", iban="CH9300762011623852957",
                         deadline_period_value=10, deadline_period_unit="days", deadline_start_event="delivery")
    letter.delivery_date = date(2026, 10, 8)
    page = Page(id="p", filename="f", sha256="s", ocr_text="Zahlungsbefehl")
    lazy = ScriptedClient(["done"])  # the model calls nothing
    result = verify.verify(lazy, letter, [page], "BE", date(2026, 10, 10))
    assert sorted(result.orchestrator_forced_tools) == ["compute_deadline", "lookup_authority", "match_scam_patterns", "validate_iban"]
    assert result.deadline.due_date == date(2026, 10, 19) and result.iban_valid and result.authority_id

    diligent = ScriptedClient([
        Response(content=None, tool_calls=[ToolCall("1", "lookup_authority", {"sender_name": "x"}),
                                           ToolCall("2", "match_scam_patterns", {"letter_id": "x"})]),
        "done",
    ])
    result = verify.verify(diligent, letter, [page], "BE", date(2026, 10, 10))
    assert sorted(result.orchestrator_forced_tools) == ["compute_deadline", "validate_iban"]


def test_tool_loop_stops_after_six_calls():
    letter = make_letter("x")
    endless = ScriptedClient([Response(content=None, tool_calls=[ToolCall(str(i), "lookup_authority", {"sender_name": "x"})] * 4)
                              for i in range(5)])
    result = verify.verify(endless, letter, [Page(id="p", filename="f", sha256="s")], "BE", date(2026, 10, 10))
    assert len(result.model_tool_calls) == verify.MAX_TOOL_CALLS


def test_cross_check_flags_values_ocr_did_not_read():
    letter = make_letter("x", iban="CH9300762011623852957", reference_numbers=["2026-123-45"], letter_date=date(2026, 10, 6),
                         amount_due=Money(amount=Decimal("1240.00"))).facts
    good = "Bern, 6. Oktober 2026 Rechnung 2026-123-45 Total CHF 1'240.00 Konto CH93 0076 2011 6238 5295 7"
    assert set(verify.cross_check(letter, good).values()) == {"match"}
    bad = "Bern, 8. Oktober 2026 Rechnung 2026-128-45 Total CHF 1'248.00 Konto CH93 0076 2011 6238 5295 1"
    assert set(verify.cross_check(letter, bad).values()) == {"mismatch"}
    assert verify.cross_check(letter, "")["iban"] == "ocr_missing"


def test_unsupported_sentences_are_dropped_and_warning_is_guaranteed():
    facts = make_letter("x", evidence_items=[{"id": "e1", "text": "Mahnung"}]).facts
    out = explain.ExplanationOut(
        what_this_is=[Sentence(text="Das ist eine Mahnung.", support=["e1"]), Sentence(text="Erfunden.", support=["e9"])],
        what_they_want=[Sentence(text="Ohne Beleg.", support=[])], deadline=[], what_you_can_do=[Sentence(text="Zahlen.", support=["e1"])],
        who_to_contact=[],
    )
    clean = explain.enforce_rules(out, facts, Verification(), "de")
    assert [s.text for s in clean.what_this_is] == ["Das ist eine Mahnung."] and clean.what_they_want == []
    flagged = explain.enforce_rules(out, facts, Verification(red_flags=[RedFlag(code="X", severity="high", evidence="e")]), "de")
    assert flagged.what_this_is[0].text.startswith("Vorsicht")
    assert [s.support for s in flagged.what_you_can_do] == [["flags"]], "no option from a flagged letter is offered"


def test_date_token_is_replaced_by_the_engine_date():
    explanation = Explanation(language="sq", what_this_is=[], what_they_want=[], what_you_can_do=[], who_to_contact=[],
                              deadline=[Sentence(text=f"Dita e fundit: {DUE_DATE_TOKEN}.", support=["e1"])])
    rendered = explain.render_explanation(explanation, due(9))
    assert rendered.deadline[0].text == "Dita e fundit: e hënë, 19 tetor 2026."
    open_date = explain.render_explanation(explanation, due(None, needs=True))
    assert "data ende e hapur" in open_date.deadline[0].text


def test_back_translation_check_sets_low_confidence():
    letter = make_letter("x", amount_due=Money(amount=Decimal("1240.00")))
    german = Explanation(language="de", what_this_is=[Sentence(text="Das ist ein Zahlungsbefehl von Alpenblick Versand AG.", support=["e1"])],
                         what_they_want=[Sentence(text="Sie sollen CHF 1’240.00 bezahlen.", support=["e1"])],
                         deadline=[Sentence(text=f"Letzter Tag: {DUE_DATE_TOKEN}.", support=["e1"])], what_you_can_do=[], who_to_contact=[])
    target = german.model_copy(update={"language": "sq"})
    faithful = check.check(ScriptedClient([german.text()]), letter, target, german)
    assert faithful.backtranslation_chrf == 100.0 and not faithful.low_confidence
    lost_date = check.check(ScriptedClient([german.text().replace(DUE_DATE_TOKEN, "19. Oktober")]), letter, target, german)
    assert lost_date.low_confidence and "date" in lost_date.failed_field_checks
    wrong_amount = check.check(ScriptedClient([german.text().replace("1’240", "1’420")]), letter, target, german)
    assert wrong_amount.low_confidence and "amount" in wrong_amount.failed_field_checks
    garbled = check.check(ScriptedClient(["Etwas ganz anderes steht hier geschrieben."]), letter, target, german)
    assert garbled.low_confidence and garbled.backtranslation_chrf < 50
