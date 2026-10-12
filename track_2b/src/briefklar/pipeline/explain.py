"""Pass 3: explain the letter in the client's language and in simple German (thinking on, no tools).

The model never writes the deadline date. It writes the token [[DUE_DATE]]; `render_explanation`
replaces it with the date from the deadline engine, localised with its weekday. A delivery date
entered later therefore changes the explanation without another model call.
"""

from __future__ import annotations

import json
from functools import lru_cache

import yaml
from pydantic import BaseModel

from briefklar import i18n
from briefklar.config import KNOWLEDGE_DIR
from briefklar.i18n import DUE_DATE_TOKEN
from briefklar.llm import prompts
from briefklar.llm.client import LLMClient
from briefklar.models import (
    EXPLANATION_SECTIONS, DeadlineResult, Explanation, Letter, LetterFacts, Sentence, Verification,
)

READING_LEVEL = "simple, about CEFR A2"
FLAGS_SUPPORT_ID = "flags"


class ExplanationOut(BaseModel):
    what_this_is: list[Sentence]
    what_they_want: list[Sentence]
    deadline: list[Sentence]
    what_you_can_do: list[Sentence]
    who_to_contact: list[Sentence]


@lru_cache
def load_card(letter_type: str, lang: str) -> dict | None:
    """Explainer card (spec 9.5): the only background knowledge Pass 3 may use besides the letter."""
    path = KNOWLEDGE_DIR / "explainers" / f"{letter_type}.{lang}.md"
    if not path.is_file():
        return None
    _, front, body = path.read_text(encoding="utf-8").split("---", 2)
    meta = yaml.safe_load(front)
    return {"id": f"card:{letter_type}.{lang}", "text": body.strip(), "sources": meta.get("sources") or []}


def facts_block(facts: LetterFacts, verification: Verification) -> str:
    def ids(field: str) -> str:
        found = facts.evidence.get(field, [])
        return f" [{', '.join(found)}]" if found else ""

    lines = ["FACTS (phrases copied from the letter; cite by id):"]
    lines += [f'{item.id}: "{item.text}"' for item in facts.evidence_items]
    lines.append("")
    lines.append("VERIFIED FACTS:")
    lines.append(f"letter_type: {facts.letter_type}")
    if facts.sender_name:
        lines.append(f"sender: {facts.sender_name}{ids('sender_name')}")
    if facts.creditor_name:
        lines.append(f"creditor: {facts.creditor_name}{ids('creditor_name')}")
    if facts.amount_due:
        lines.append(f"amount_due: {facts.amount_due.currency} {facts.amount_due.amount:.2f}{ids('amount_due')}")
    if facts.demanded_action:
        lines.append(f"demanded_action: {facts.demanded_action}{ids('demanded_action')}")
    deadline = verification.deadline
    if deadline is None:
        lines.append("deadline: none stated in the letter")
    else:
        basis = "fixed date printed on the letter" if deadline.start_event == "fixed_date" else (
            f"{deadline.period_value} {deadline.period_unit} from {str(deadline.start_event).replace('_', ' ')}"
        )
        lines.append(f"deadline: {DUE_DATE_TOKEN} (computed by the deadline engine; {basis}){ids('deadline_text')}")
    options = "; ".join(f'"{o}"' for o in facts.stated_options) or "none"
    lines.append(f"options stated in the letter: {options}{ids('stated_options')}")
    contact = verification.authority_contact
    if contact and contact.get("sourced"):
        details = ", ".join(str(contact[k]) for k in ("phone", "email", "web", "address") if contact.get(k))
        lines.append(f"official contact (directory): {contact['name']}, {details}")
    elif contact:
        lines.append(f"official contact (directory): {contact['name']} (contact details not on file; say: ask the counsellor)")
    else:
        lines.append("official contact (directory): none on file; say: ask the counsellor")
    if verification.red_flags:
        lines.append(f"red flags (cite as {FLAGS_SUPPORT_ID}):")
        lines += [f"- {flag.code}: {flag.evidence}" for flag in verification.red_flags]
    else:
        lines.append("red flags: none")
    return "\n".join(lines)


def build_messages(facts: LetterFacts, verification: Verification, target: str) -> list[dict]:
    language = i18n.languages()[target]["english"]
    system = prompts.load("explain").format(target_language=language, reading_level=READING_LEVEL)
    schema = json.dumps(ExplanationOut.model_json_schema(), ensure_ascii=False, sort_keys=True)
    card = load_card(facts.letter_type, facts.source_language)
    card_block = f"CARD ({card['id']}):\n{card['text']}" if card else "CARD: none for this letter type"
    return [
        {"role": "system", "content": f"{system}\n\nJSON schema:\n{schema}"},
        {"role": "user", "content": f"{facts_block(facts, verification)}\n\n{card_block}"},
    ]


def enforce_rules(out: ExplanationOut, facts: LetterFacts, verification: Verification, target: str) -> Explanation:
    """Drop unsupported sentences; with red flags, guarantee the warning line and withhold the letter's options."""
    valid = {item.id for item in facts.evidence_items} | {FLAGS_SUPPORT_ID}
    sections: dict[str, list[Sentence]] = {}
    for name in EXPLANATION_SECTIONS:
        kept = []
        for sentence in getattr(out, name):
            support = [s for s in sentence.support if s in valid or s.startswith("card:")]
            if support and sentence.text.strip():
                kept.append(Sentence(text=sentence.text.strip(), support=support))
        sections[name] = kept
    if verification.red_flags:
        warning = i18n.t("be_careful", target)
        first = sections["what_this_is"][0].text if sections["what_this_is"] else ""
        if warning.casefold() not in first.casefold():
            sections["what_this_is"].insert(0, Sentence(text=warning, support=[FLAGS_SUPPORT_ID]))
        # Deterministic guard: with warning signs, no option from the letter is offered to the client.
        sections["what_you_can_do"] = [Sentence(text=i18n.t("flagged_wait", target), support=[FLAGS_SUPPORT_ID])]
    return Explanation(language=target, **sections)  # type: ignore[arg-type]


def explain(client: LLMClient, letter: Letter, target: str) -> Explanation:
    facts, verification = letter.facts, letter.verification
    assert facts is not None and verification is not None
    out = client.chat_json(
        build_messages(facts, verification, target), ExplanationOut,
        thinking=True, pass_name=f"explain:{target}", letter_id=letter.id, label=letter.label or "",
    )
    return enforce_rules(out, facts, verification, target)


def due_date_text(deadline: DeadlineResult | None, lang: str) -> str:
    if deadline is not None and deadline.due_date is not None:
        return i18n.format_long_date(deadline.due_date, lang)
    return i18n.t("date_needed", lang)


def render_explanation(explanation: Explanation, deadline: DeadlineResult | None) -> Explanation:
    """A copy with [[DUE_DATE]] replaced by the verified, localised date."""
    replacement = due_date_text(deadline, explanation.language)
    rendered = explanation.model_copy(deep=True)
    for sentence in rendered.sentences():
        sentence.text = sentence.text.replace(DUE_DATE_TOKEN, replacement)
    return rendered
