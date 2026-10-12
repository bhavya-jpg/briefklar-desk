"""Reply pass (spec section 8.6): fill vetted templates from facts.

Templates carry the fixed wording. The model may only pick values that are in the facts, and draft
the few free-text slots; those are always marked for review. Fixed wording that still lacks an
official source is never generated: the draft is returned with that slot listed in `missing`.
"""

from __future__ import annotations

import json
import secrets
from datetime import date
from functools import lru_cache

import yaml
from jinja2 import Environment, StrictUndefined, UndefinedError, meta
from pydantic import BaseModel

from briefklar import i18n
from briefklar.config import KNOWLEDGE_DIR
from briefklar.llm import prompts
from briefklar.llm.client import LLMClient
from briefklar.models import Letter, LetterFacts, ReplyDraft

TEMPLATE_DIR = KNOWLEDGE_DIR / "reply_templates"
PLACEHOLDER = "[ … ]"
SOURCE_REQUIRED = "[SOURCE REQUIRED]"
TEMPLATE_IDS = ("objection_payment_order", "extension_request", "instalment_request")

_env = Environment(undefined=StrictUndefined, autoescape=False, keep_trailing_newline=False)


class MissingSlots(ValueError):
    def __init__(self, slots: list[str]):
        super().__init__(f"reply template slots missing: {', '.join(slots)}")
        self.slots = slots


class SlotOut(BaseModel):
    value: str | None = None
    support: list[str] = []


class ReplyOut(BaseModel):
    slots: dict[str, SlotOut]


@lru_cache
def load_template(template_id: str, lang: str) -> dict:
    path = TEMPLATE_DIR / f"{template_id}.{lang}.md"
    if not path.is_file():
        raise FileNotFoundError(f"no reply template {template_id!r} in {lang!r}")
    _, front, body = path.read_text(encoding="utf-8").split("---", 2)
    template = yaml.safe_load(front)
    template["body"] = body.strip() + "\n"
    template["slots"] = sorted(meta.find_undeclared_variables(_env.parse(template["body"])))
    template.setdefault("fixed", {})
    template.setdefault("free_text", [])
    return template


def available_templates(facts: LetterFacts) -> list[dict]:
    out = []
    for template_id in TEMPLATE_IDS:
        try:
            template = load_template(template_id, facts.source_language)
        except FileNotFoundError:
            continue
        if facts.letter_type in template.get("applies_to", []) or "*" in template.get("applies_to", []):
            unsourced = [slot for slot, text in template["fixed"].items() if not text]
            out.append({"id": template_id, "title": template["title"], "unsourced": unsourced})
    return out


def render_template(template: dict, slots: dict[str, str]) -> str:
    """Render with every slot present and non-empty. Raises MissingSlots otherwise (spec 17.3)."""
    missing = [name for name in sorted(set(template["required"]) | set(template["slots"])) if not slots.get(name)]
    if missing:
        raise MissingSlots(missing)
    try:
        return _env.from_string(template["body"]).render(**slots).strip() + "\n"
    except UndefinedError as exc:
        raise MissingSlots([str(exc)]) from exc


def fact_slots(facts: LetterFacts, due_date: date | None, today: date) -> dict[str, tuple[str | None, list[str]]]:
    """Slot values that come straight from the facts: name -> (value, evidence ids)."""

    def ev(*fields: str) -> list[str]:
        return [i for f in fields for i in facts.evidence.get(f, [])]

    def numeric(d: date | None) -> str | None:
        return f"{d.day:02d}.{d.month:02d}.{d.year}" if d else None

    def lines(address: str | None) -> str | None:
        return "\n".join(part.strip() for part in address.split(",")) if address else None

    reference = facts.reference_numbers[0] if facts.reference_numbers else None
    return {
        "debtor_name": (facts.recipient_name, ev("recipient_name")),
        "debtor_address": (lines(facts.recipient_address), ev("recipient_address")),
        "office_name": (facts.sender_name, ev("sender_name")),
        "office_address": (lines(facts.sender_address), ev("sender_address")),
        "enforcement_number": (reference, ev("reference_numbers")),
        "reference": (reference, ev("reference_numbers")),
        "creditor_name": (facts.creditor_name or facts.sender_name, ev("creditor_name", "sender_name")),
        "amount": (i18n.format_money(facts.amount_due.amount, facts.amount_due.currency) if facts.amount_due else None,
                   ev("amount_due", "amounts")),
        "letter_date": (numeric(facts.letter_date), ev("letter_date")),
        "due_date": (numeric(due_date), ev("deadline_text")),
        "date": (numeric(today), []),
        "signature_line": (facts.recipient_name, ev("recipient_name")),
        "place": (None, []),  # the counsellor types it
    }


def build_messages(template: dict, facts: LetterFacts) -> list[dict]:
    schema = json.dumps(ReplyOut.model_json_schema(), ensure_ascii=False, sort_keys=True)
    language = {"de": "German", "fr": "French", "it": "Italian"}[template["lang"]]
    wanted = [s for s in template["slots"] if s not in template["fixed"] and s not in ("date", "place")]
    slot_lines = [f"- {s}" + (" (free text)" if s in template["free_text"] else "") for s in wanted]
    evidence = "\n".join(f'{item.id}: "{item.text}"' for item in facts.evidence_items)
    payload = facts.model_dump(mode="json", exclude={"evidence_items"})
    return [
        {"role": "system", "content": f"{prompts.load('reply').format(language=language)}\n\nJSON schema:\n{schema}"},
        {"role": "user", "content":
            f"TEMPLATE: {template['id']} ({template['title']})\nSLOTS:\n" + "\n".join(slot_lines)
            + f"\n\nFACTS:\n{json.dumps(payload, ensure_ascii=False, sort_keys=True)}\n\nEVIDENCE:\n{evidence}"},
    ]


def _in_facts(value: str, facts: LetterFacts) -> bool:
    haystack = json.dumps(facts.model_dump(mode="json", exclude={"evidence"}), ensure_ascii=False).casefold()
    return " ".join(value.split()).casefold() in " ".join(haystack.split())


def assemble(template: dict, slots: dict[str, str], slot_sources: dict[str, list[str]], needs_review: list[str],
             letter_id: str, reply_id: str | None = None) -> ReplyDraft:
    """Build a draft from slot values; empty or unsourced slots get a visible placeholder."""
    missing = []
    filled = dict(slots)
    for name in sorted(set(template["required"]) | set(template["slots"])):
        if name in template["fixed"]:
            if template["fixed"][name]:
                filled[name] = template["fixed"][name]
            else:
                filled[name] = SOURCE_REQUIRED
                missing.append(name)
        elif not (filled.get(name) or "").strip() or filled[name] == PLACEHOLDER:
            filled[name] = PLACEHOLDER
            missing.append(name)
    return ReplyDraft(
        id=reply_id or secrets.token_urlsafe(8), letter_id=letter_id,
        template_id=template["id"], language=template["lang"],
        slots=filled, slot_sources=slot_sources, needs_review=needs_review,
        rendered_text=render_template(template, filled), missing=missing,
    )


def draft_reply(client: LLMClient, letter: Letter, template_id: str, today: date) -> ReplyDraft:
    facts = letter.facts
    assert facts is not None
    template = load_template(template_id, facts.source_language)
    deadline = letter.verification.deadline if letter.verification else None
    known = fact_slots(facts, deadline.due_date if deadline else None, today)
    out = client.chat_json(build_messages(template, facts), ReplyOut,
                           pass_name=f"reply:{template_id}", letter_id=letter.id, label=letter.label or "")
    valid_ids = {item.id for item in facts.evidence_items}
    slots: dict[str, str] = {}
    sources: dict[str, list[str]] = {}
    needs_review: list[str] = []
    for name in template["slots"]:
        if name in template["fixed"]:
            continue
        proposed = out.slots.get(name)
        value, support = known.get(name, (None, []))
        if name in template["free_text"]:
            value = (proposed.value if proposed and proposed.value else None)
            support = [s for s in (proposed.support if proposed else []) if s in valid_ids]
            needs_review.append(name)
        elif proposed and proposed.value and name not in ("date", "place") and _in_facts(proposed.value, facts):
            # the model may choose among values that are on the letter (e.g. which reference number)
            if name in ("enforcement_number", "reference") or value is None:
                value = proposed.value.strip()
                support = [s for s in proposed.support if s in valid_ids] or support
        slots[name] = value or ""
        sources[name] = support
    return assemble(template, slots, sources, needs_review, letter.id)


def update_reply(draft: ReplyDraft, slots: dict[str, str]) -> ReplyDraft:
    """Apply counsellor edits. Fixed wording cannot be edited."""
    template = load_template(draft.template_id, draft.language)
    merged = {**draft.slots, **{k: v for k, v in slots.items() if k in template["slots"] and k not in template["fixed"]}}
    return assemble(template, merged, draft.slot_sources, draft.needs_review, draft.letter_id, reply_id=draft.id)
