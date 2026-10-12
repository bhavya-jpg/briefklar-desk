"""Fixture backend: a deterministic stand-in for the model. NOT a model and NOT Apertus.

It answers each pass from the generator's gold data and a stock of hand-written sentences, so that the
pipeline, the UI, the printouts and `make run` can be exercised end to end before a GPU is available.
Its answers are near-perfect by construction and say nothing about how Apertus performs. Records made
with it are marked `"backend": "fixture"`; the app header and the eval summary repeat that.

Select it with LLM_BASE_URL=fixture://gold (see bench/fixtures/record.py).
"""

from __future__ import annotations

import json
import re
from contextvars import ContextVar
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import yaml

from briefklar import i18n
from briefklar.models import RULE_FAMILY_BY_TYPE

# Set by the recorder: {"gold": <letter gold>} for letter passes, {"case": {...}} for the case pass.
CURRENT: ContextVar[dict | None] = ContextVar("fixture_current", default=None)


@lru_cache
def phrases() -> dict:
    return yaml.safe_load((Path(__file__).parent / "phrases.yaml").read_text(encoding="utf-8"))


def _sentence(key: str, lang: str, **params: str) -> str:
    return phrases()["sentences"][key][lang].format(**params)


def _ids(facts: dict, *fields: str) -> list[str]:
    return [i for f in fields for i in facts["evidence"].get(f, [])]


def explanation(gold: dict, lang: str, prompt: str) -> dict:
    facts = gold["facts"]
    flagged = "red flags: none" not in prompt
    has_deadline = "deadline: none" not in prompt
    money = facts["amount_due"]
    amount = i18n.format_money(Decimal(money["amount"]), money["currency"]) if money else None

    what = []
    if flagged:
        what.append({"text": i18n.t("be_careful", lang), "support": ["flags"]})
    kind = phrases()["types"][facts["letter_type"]][lang]
    what.append({"text": _sentence("this_is", lang, type=kind, sender=facts["sender_name"]),
                 "support": _ids(facts, "letter_type", "sender_name")})

    if amount and facts["demanded_action"]:
        want = [{"text": _sentence("want_pay", lang, amount=amount), "support": _ids(facts, "amount_due", "demanded_action")}]
    elif facts["demanded_action"]:
        want = [{"text": _sentence("want_action", lang), "support": _ids(facts, "demanded_action")}]
    else:
        want = [{"text": _sentence("want_info", lang), "support": _ids(facts, "letter_type")}]

    if has_deadline:
        deadline = [{"text": _sentence("deadline", lang), "support": _ids(facts, "deadline_text")}]
    else:
        deadline = [{"text": _sentence("no_deadline", lang), "support": _ids(facts, "letter_type")}]

    options = []
    if flagged:  # the product replaces this section anyway (pipeline/explain.py: enforce_rules)
        options = [{"text": i18n.t("flagged_wait", lang), "support": ["flags"]}]
    for key, evidence_id in zip(gold["option_keys"], facts["evidence"].get("stated_options", [])):
        if flagged:
            break
        options.append({"text": _sentence(f"opt_{key}", lang), "support": [evidence_id]})
    if not options:
        options = [{"text": _sentence("opt_none", lang), "support": _ids(facts, "letter_type")}]

    official = re.search(r"^official contact \(directory\): (.+)$", prompt, re.M)
    line = official.group(1) if official else ""
    if line and "say: ask the counsellor" not in line:
        contact = [{"text": _sentence("contact_official", lang, contact=line), "support": _ids(facts, "sender_name")}]
    else:
        contact = [{"text": _sentence("contact_counsellor", lang), "support": _ids(facts, "sender_name")}]

    return {"what_this_is": what, "what_they_want": want, "deadline": deadline,
            "what_you_can_do": options, "who_to_contact": contact}


def explanation_text(data: dict) -> str:
    return "\n".join(s["text"] for section in data.values() for s in section)


class FixtureBackend:
    name = "fixture"

    def __init__(self) -> None:
        self._german: dict[str, str] = {}

    def complete(self, *, messages: list[dict], schema, tools, thinking: bool, meta: dict) -> dict:
        current = CURRENT.get()
        if current is None:
            raise RuntimeError("fixture backend used outside bench.fixtures.record (no gold in context)")
        name = meta["pass"]
        user = messages[1]["content"]
        if name == "extract":
            return {"content": json.dumps(current["gold"]["facts"], ensure_ascii=False)}
        if name == "verify":
            return self._verify(current["gold"], messages)
        if name.startswith("explain:"):
            lang = name.split(":", 1)[1]
            data = explanation(current["gold"], lang, user)
            if lang == "de":
                self._german[current["gold"]["id"]] = explanation_text(data)
            return {"content": json.dumps(data, ensure_ascii=False)}
        if name.startswith("check:"):
            gold = current["gold"]
            if gold["id"] not in self._german:
                self._german[gold["id"]] = explanation_text(explanation(gold, "de", current.get("prompt_de", "")))
            return {"content": self._german[gold["id"]]}
        if name == "case":
            return {"content": json.dumps(self._case(current["case"], json.loads(user)), ensure_ascii=False)}
        if name.startswith("reply:"):
            return {"content": json.dumps(self._reply(current["gold"], user), ensure_ascii=False)}
        raise RuntimeError(f"fixture backend has no answer for pass {name!r}")

    @staticmethod
    def _verify(gold: dict, messages: list[dict]) -> dict:
        if any(m["role"] == "tool" for m in messages):
            return {"content": "done"}
        facts = gold["facts"]
        context = json.loads(messages[1]["content"])
        calls = []

        def call(name: str, arguments: dict) -> None:
            calls.append({"id": f"call_{len(calls) + 1}", "name": name, "arguments": arguments})

        if facts["deadline_start_event"]:
            call("compute_deadline", {
                "rule_family": RULE_FAMILY_BY_TYPE[facts["letter_type"]],
                "period_value": facts["deadline_period_value"] or 0,
                "period_unit": facts["deadline_period_unit"] or "days",
                "start_event": facts["deadline_start_event"],
                "letter_date": facts["letter_date"], "fixed_date": facts["deadline_fixed_date"],
                "canton": context["canton"],
            })
        if facts["iban"]:
            call("validate_iban", {"iban": facts["iban"]})
        if context["qr_code_found"]:
            call("decode_qr_bill", {})
        call("lookup_authority", {"sender_name": facts["sender_name"], "sender_address": facts["sender_address"]})
        call("match_scam_patterns", {"letter_id": context["letter_id"]})
        return {"content": None, "tool_calls": calls}

    @staticmethod
    def _case(case: dict, payload: list[dict]) -> dict:
        refs = {gold_id: item["id"] for gold_id, item in zip(case["letter_ids"], payload)}
        threads = [
            {"letter_ids": [refs[i] for i in ids if i in refs], "reason": "same creditor and reference"}
            for ids in case["gold_threads"] if sum(i in refs for i in ids) >= 2
        ]
        by_ref = {item["id"]: item for item in payload}
        order = []
        for gold_id in case["gold_order"]:
            if gold_id not in refs:
                continue
            item = by_ref[refs[gold_id]]
            if item["red_flags"]:
                reason = "warning signs: look at this first"
            elif item["due_date"]:
                reason = f"deadline {item['due_date']}"
            elif item["needs_delivery_date"]:
                reason = "deadline depends on the delivery date"
            else:
                reason = "no deadline"
            order.append({"letter_id": refs[gold_id], "reason": reason})
        return {"threads": threads, "order": order}

    @staticmethod
    def _reply(gold: dict, prompt: str) -> dict:
        facts = gold["facts"]
        lang = facts["source_language"]
        mapping = {
            "debtor_name": (facts["recipient_name"], "recipient_name"),
            "debtor_address": (facts["recipient_address"], "recipient_address"),
            "office_name": (facts["sender_name"], "sender_name"),
            "office_address": (facts["sender_address"], "sender_address"),
            "enforcement_number": (facts["reference_numbers"][0] if facts["reference_numbers"] else None, "reference_numbers"),
            "reference": (facts["reference_numbers"][0] if facts["reference_numbers"] else None, "reference_numbers"),
            "signature_line": (facts["recipient_name"], "recipient_name"),
        }
        slots = {}
        for line in prompt.split("SLOTS:\n", 1)[1].split("\n\n", 1)[0].splitlines():
            name = line.removeprefix("- ").split(" ")[0]
            if "(free text)" in line:
                slots[name] = {"value": phrases()["reply_free_text"][name][lang], "support": []}
            elif name in mapping:
                value, field = mapping[name]
                slots[name] = {"value": value, "support": facts["evidence"].get(field, [])[:1]}
            else:
                slots[name] = {"value": None, "support": []}
        return {"slots": slots}
