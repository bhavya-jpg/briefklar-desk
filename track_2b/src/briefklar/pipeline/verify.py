"""Pass 2: verify the extracted facts with deterministic tools (tool calling, thinking off).

Apertus is offered the tools and asked to verify the letter; the orchestrator executes each call.
Tools the model should have called but did not are called by the orchestrator, and that is recorded.
The final Verification is always built from the tool functions themselves, never from model text.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation

from briefklar.llm import prompts
from briefklar.llm.client import LLMClient
from briefklar.models import RULE_FAMILY_BY_TYPE, DeadlineResult, Letter, LetterFacts, Page, Verification
from briefklar.tools import authority as authority_tool
from briefklar.tools import qrbill
from briefklar.tools.deadline import compute_deadline
from briefklar.tools.iban import compact, validate_iban
from briefklar.tools.scam import run_checks

MAX_TOOL_CALLS = 6

TOOLS = [
    {"type": "function", "function": {
        "name": "compute_deadline",
        "description": "Compute the last day to act, using Swiss rules. Never compute dates yourself.",
        "parameters": {"type": "object", "required": ["rule_family", "period_value", "period_unit", "start_event"],
                       "properties": {
                           "rule_family": {"type": "string", "enum": ["schkg", "generic_admin", "contract", "none"]},
                           "period_value": {"type": "integer"},
                           "period_unit": {"type": "string", "enum": ["days", "months"]},
                           "start_event": {"type": "string", "enum": ["delivery", "letter_date", "fixed_date"]},
                           "letter_date": {"type": ["string", "null"]},
                           "fixed_date": {"type": ["string", "null"]},
                           "canton": {"type": "string"}}}}},
    {"type": "function", "function": {
        "name": "validate_iban", "description": "Check IBAN checksum and country.",
        "parameters": {"type": "object", "required": ["iban"], "properties": {"iban": {"type": "string"}}}}},
    {"type": "function", "function": {
        "name": "decode_qr_bill", "description": "Return the parsed Swiss QR-bill found on the letter, if any.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "lookup_authority",
        "description": "Look up the claimed sender in the local directory of Swiss authorities.",
        "parameters": {"type": "object", "required": ["sender_name"],
                       "properties": {"sender_name": {"type": "string"},
                                      "sender_address": {"type": ["string", "null"]}}}}},
    {"type": "function", "function": {
        "name": "match_scam_patterns",
        "description": "Check the letter text and facts against known scam patterns.",
        "parameters": {"type": "object", "required": ["letter_id"], "properties": {"letter_id": {"type": "string"}}}}},
]

_MONTHS = {
    "de": ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
           "November", "Dezember"],
    "fr": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
           "novembre", "décembre"],
    "it": ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
           "ottobre", "novembre", "dicembre"],
}
_AMOUNT = re.compile(r"(?<![\d.])\d{1,3}(?:['’‘`´   ]\d{3})+(?:[.,]\d{2})?(?!\d)|(?<![\d.'’])\d+[.,]\d{2}(?!\d)")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,4})?\b")
_DATE_LIKE = re.compile(r"\b\d{1,2}\.\s?\d{1,2}\.\s?\d{2,4}\b|\b\d{1,2}\.?\s+[A-Za-zäéûô]{3,10}\s+\d{4}\b")


# -- deterministic parts -------------------------------------------------------------------------


def qr_from_pages(pages: list[Page]) -> dict | None:
    for page in pages:
        for payload in page.qr_payloads:
            if qrbill.is_qr_bill(payload):
                try:
                    return qrbill.parse_qr_bill(payload)
                except ValueError:
                    continue
    return None


def deadline_for(facts: LetterFacts, delivery_date: date | None, canton: str, today: date) -> DeadlineResult | None:
    """The deadline for a letter, from its extracted facts. None when the letter sets no deadline."""
    start_event = facts.deadline_start_event
    if start_event is None and facts.deadline_fixed_date:
        start_event = "fixed_date"
    if start_event is None:
        return None
    start = {"delivery": delivery_date, "letter_date": facts.letter_date, "fixed_date": facts.deadline_fixed_date}[
        start_event
    ]
    return compute_deadline(
        rule_family=RULE_FAMILY_BY_TYPE[facts.letter_type],
        period_value=facts.deadline_period_value,
        period_unit=facts.deadline_period_unit,
        start_event=start_event,
        start_date=start,
        canton=canton,
        today=today,
    )


def _digits(text: str) -> str:
    return "".join(str(unicodedata.digit(ch)) if ch.isdigit() else ch for ch in text)


def _amount_cents(raw: str) -> int | None:
    cleaned = re.sub(r"['’‘`´   ]", "", raw).replace(",", ".")
    try:
        return int((Decimal(cleaned) * 100).to_integral_value())
    except InvalidOperation:
        return None


def _date_forms(d: date) -> list[str]:
    forms = [f"{d.day:02d}.{d.month:02d}.{d.year}", f"{d.day}.{d.month}.{d.year}", f"{d.day:02d}.{d.month:02d}.{d.year % 100:02d}"]
    for months in _MONTHS.values():
        name = months[d.month - 1].casefold()
        forms += [f"{d.day}. {name} {d.year}", f"{d.day} {name} {d.year}", f"{d.day}er {name} {d.year}", f"{d.day}° {name} {d.year}"]
    return forms


def cross_check(facts: LetterFacts, ocr_text: str) -> dict[str, str]:
    """Compare the model's amount, IBAN, references and dates with the OCR text (F3)."""
    text = _digits(ocr_text)
    folded = re.sub(r"\s+", " ", text.casefold())
    squeezed = re.sub(r"\s+", "", text.upper())
    checks: dict[str, str] = {}

    def verdict(found: bool, ocr_has_candidates: bool) -> str:
        return "match" if found else ("mismatch" if ocr_has_candidates else "ocr_missing")

    wanted = [m.amount for m in ([facts.amount_due] if facts.amount_due else facts.amounts)]
    if wanted:
        seen = {_amount_cents(raw) for raw in _AMOUNT.findall(text)}
        checks["amounts"] = verdict(all(int(a * 100) in seen for a in wanted), bool(seen - {None}))
    if facts.iban:
        seen_ibans = {compact(raw) for raw in _IBAN.findall(text.upper())}
        checks["iban"] = verdict(compact(facts.iban) in seen_ibans or compact(facts.iban) in squeezed, bool(seen_ibans))
    if facts.reference_numbers:
        refs = [re.sub(r"\s+", "", r.upper()) for r in facts.reference_numbers]
        checks["reference_numbers"] = verdict(all(r in squeezed for r in refs), bool(squeezed))
    for field in ("letter_date", "deadline_fixed_date"):
        value = getattr(facts, field)
        if value:
            checks[field] = verdict(any(form in folded for form in _date_forms(value)), bool(_DATE_LIKE.search(text)))
    return checks


def build_verification(
    facts: LetterFacts, pages: list[Page], delivery_date: date | None, canton: str, today: date,
    model_tool_calls: list[str] | None = None,
) -> Verification:
    ocr_text = "\n".join(page.ocr_text for page in pages)
    qr = qr_from_pages(pages)
    deadline = deadline_for(facts, delivery_date, canton, today)
    iban = validate_iban(facts.iban) if facts.iban else None
    entry = authority_tool.lookup_authority(facts.sender_name)
    called = model_tool_calls or []
    required = ["lookup_authority", "match_scam_patterns"]
    if deadline is not None:
        required.append("compute_deadline")
    if facts.iban:
        required.append("validate_iban")
    return Verification(
        deadline=deadline,
        iban_valid=iban["valid"] if iban else None,
        iban_country=iban["country"] if iban else None,
        qr=qr,
        authority_id=entry["id"] if entry else None,
        authority_contact=authority_tool.contact_of(entry),
        red_flags=run_checks(facts, ocr_text, qr=qr, authority=entry),
        field_checks=cross_check(facts, ocr_text),  # type: ignore[arg-type]
        orchestrator_forced_tools=[name for name in required if name not in called],
        model_tool_calls=called,
    )


# -- tool loop -----------------------------------------------------------------------------------


def _parse_date(value) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None


def execute_tool(name: str, args: dict, *, facts: LetterFacts, pages: list[Page],
                 delivery_date: date | None, canton: str) -> dict:
    """Run one tool call. Results contain nothing that depends on today's date, so replay keys are stable."""
    if name == "compute_deadline":
        start_event = args.get("start_event")
        start = {
            "delivery": delivery_date,
            "letter_date": _parse_date(args.get("letter_date")) or facts.letter_date,
            "fixed_date": _parse_date(args.get("fixed_date")) or facts.deadline_fixed_date,
        }.get(start_event)
        try:
            result = compute_deadline(
                args.get("rule_family", "none"), args.get("period_value"), args.get("period_unit"),
                start_event, start, canton,
            )
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}
        return {
            "due_date": result.due_date.isoformat() if result.due_date else None,
            "needs_delivery_date": result.needs_delivery_date,
            "verified_rule": result.verified_rule,
            "trace": result.trace,
        }
    if name == "validate_iban":
        return validate_iban(str(args.get("iban", "")))
    if name == "decode_qr_bill":
        return qr_from_pages(pages) or {"found": False}
    if name == "lookup_authority":
        entry = authority_tool.lookup_authority(str(args.get("sender_name", "")))
        return authority_tool.contact_of(entry) or {"found": False}
    if name == "match_scam_patterns":
        text = "\n".join(page.ocr_text for page in pages)
        entry = authority_tool.lookup_authority(facts.sender_name)
        flags = run_checks(facts, text, qr=qr_from_pages(pages), authority=entry)
        return {"red_flags": [flag.model_dump() for flag in flags]}
    return {"error": f"unknown tool: {name}"}


def build_messages(facts: LetterFacts, pages: list[Page], delivery_date: date | None, canton: str,
                   letter_ref: str) -> list[dict]:
    payload = facts.model_dump(mode="json", exclude={"evidence", "evidence_items"})
    context = {
        "letter_id": letter_ref,
        "facts": payload,
        "qr_code_found": any(page.qr_payloads for page in pages),
        "canton": canton,
        "delivery_date": delivery_date.isoformat() if delivery_date else None,
    }
    return [
        {"role": "system", "content": prompts.load("verify")},
        {"role": "user", "content": json.dumps(context, ensure_ascii=False, sort_keys=True)},
    ]


def verify(client: LLMClient, letter: Letter, pages: list[Page], canton: str, today: date) -> Verification:
    facts = letter.facts
    assert facts is not None
    messages = build_messages(facts, pages, letter.delivery_date, canton, "letter")
    called: list[str] = []
    while len(called) < MAX_TOOL_CALLS:
        response = client.chat(messages, tools=TOOLS, pass_name="verify", letter_id=letter.id, label=letter.label or "")
        if not response.tool_calls:
            break
        calls = response.tool_calls[: MAX_TOOL_CALLS - len(called)]
        messages.append({"role": "assistant", "content": response.content, "tool_calls": [
            {"id": c.id, "type": "function",
             "function": {"name": c.name, "arguments": json.dumps(c.arguments, ensure_ascii=False, sort_keys=True)}}
            for c in calls
        ]})
        for call in calls:
            result = execute_tool(call.name, call.arguments, facts=facts, pages=pages,
                                  delivery_date=letter.delivery_date, canton=canton)
            called.append(call.name)
            messages.append({"role": "tool", "tool_call_id": call.id,
                             "content": json.dumps(result, ensure_ascii=False, sort_keys=True, default=str)})
    return build_verification(facts, pages, letter.delivery_date, canton, today, model_tool_calls=called)
