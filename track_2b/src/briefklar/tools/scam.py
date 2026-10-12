"""Red-flag checks (spec section 9.3).

Every check returns evidence, never a verdict: the words "fake", "scam" or "real" are not produced here.
"""

from __future__ import annotations

import re
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import yaml
from rapidfuzz import fuzz

from briefklar.config import KNOWLEDGE_DIR
from briefklar.models import LetterFacts, RedFlag
from briefklar.tools.authority import normalise
from briefklar.tools.iban import SWISS_IBAN_COUNTRIES, compact

QR_NAME_MATCH_THRESHOLD = 60

_PHONE = re.compile(r"(?:\+|00)\d[\d\s./-]{7,}\d|\b0\d{2}[\s./-]?\d{3}[\s./-]?\d{2}[\s./-]?\d{2}\b")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_WEB = re.compile(r"(?:https?://|www\.)[\w.-]+\.[a-z]{2,}|\b[\w-]+(?:\.[\w-]+)*\.(?:ch|li|com|org|net|info|admin\.ch)\b", re.I)


@lru_cache
def load_patterns(path: Path | None = None) -> dict:
    return yaml.safe_load((path or KNOWLEDGE_DIR / "scam_patterns.yaml").read_text(encoding="utf-8"))


def claims_authority(facts: LetterFacts, authority: dict | None, patterns: dict) -> bool:
    if authority is not None or facts.letter_type in patterns.get("authority_letter_types", []):
        return True
    sender = normalise(facts.sender_name or "")
    words = sender.split()
    for keyword in (k for group in patterns.get("authority_keywords", {}).values() for k in group):
        key = normalise(keyword)
        if " " in key:
            if key in sender:
                return True
        elif any(word.startswith(key) or word.endswith(key) for word in words):
            return True
    return False


def _spans(facts: LetterFacts, *fields: str) -> list[str]:
    return [eid for field in fields for eid in facts.evidence.get(field, [])]


def _context(text: str, term: str, width: int = 60) -> str:
    index = text.casefold().find(term.casefold())
    if index < 0:
        return term
    start, end = max(0, index - width), min(len(text), index + len(term) + width)
    return " ".join(text[start:end].split())


def _phone_digits(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if digits.startswith("0041"):
        digits = digits[4:]
    elif digits.startswith("41") and len(digits) == 11:
        digits = digits[2:]
    return digits.lstrip("0")


def _domain(value: str) -> str:
    value = value.casefold().split("@")[-1]
    value = re.sub(r"^https?://", "", value).split("/")[0]
    return value.removeprefix("www.")


def check_sender_in_directory(facts: LetterFacts, authority: dict | None, patterns: dict) -> list[RedFlag]:
    if authority is not None or not facts.sender_name or not claims_authority(facts, None, patterns):
        return []
    return [RedFlag(
        code="SENDER_NOT_IN_DIRECTORY",
        severity="warn",
        evidence=f'The sender "{facts.sender_name}" presents itself as an authority but is not in the local directory.',
        span_ids=_spans(facts, "sender_name"),
    )]


def check_contact_mismatch(facts: LetterFacts, authority: dict | None) -> list[RedFlag]:
    if authority is None or not facts.sender_contact:
        return []
    printed = facts.sender_contact
    flags: list[RedFlag] = []

    def flag(kind: str, on_letter: str, official: str) -> None:
        flags.append(RedFlag(
            code="CONTACT_MISMATCH",
            severity="high",
            evidence=f'The {kind} on the letter ("{on_letter}") differs from the directory entry ("{official}").',
            span_ids=_spans(facts, "sender_contact"),
        ))

    if authority.get("phone"):
        official = _phone_digits(authority["phone"])
        for phone in _PHONE.findall(printed):
            if _phone_digits(phone) != official:
                flag("phone number", phone.strip(), authority["phone"])
    official_domains = {_domain(authority[k]) for k in ("web", "email") if authority.get(k)}
    if official_domains:
        emails = _EMAIL.findall(printed)
        webs = [w for w in _WEB.findall(_EMAIL.sub(" ", printed))]
        for kind, values in (("e-mail address", emails), ("web address", webs)):
            for value in values:
                domain = _domain(value)
                if not any(domain == d or domain.endswith("." + d) for d in official_domains):
                    flag(kind, value, ", ".join(sorted(official_domains)))
    return flags


def check_foreign_iban(facts: LetterFacts, authority: dict | None, qr: dict | None, patterns: dict) -> list[RedFlag]:
    if not claims_authority(facts, authority, patterns):
        return []
    flags = []
    for source, iban in (("printed on the letter", facts.iban), ("in the QR code", (qr or {}).get("iban"))):
        value = compact(iban or "")
        if len(value) >= 2 and value[:2].isalpha() and value[:2] not in SWISS_IBAN_COUNTRIES:
            flags.append(RedFlag(
                code="FOREIGN_IBAN_FOR_AUTHORITY",
                severity="high",
                evidence=f"The sender presents itself as a Swiss authority, but the IBAN {source} is from {value[:2]} ({value}).",
                span_ids=_spans(facts, "iban"),
            ))
    return flags[:1]


def check_qr_mismatch(facts: LetterFacts, qr: dict | None) -> list[RedFlag]:
    if not qr:
        return []
    flags = []
    qr_iban = compact(qr.get("iban") or "")
    if facts.iban and qr_iban and compact(facts.iban) != qr_iban:
        flags.append(RedFlag(
            code="QR_MISMATCH", severity="high",
            evidence=f"The IBAN in the QR code ({qr_iban}) differs from the printed IBAN ({compact(facts.iban)}).",
            span_ids=_spans(facts, "iban"),
        ))
    if qr.get("amount") and facts.amounts:
        qr_amount = Decimal(qr["amount"])
        if all(m.amount != qr_amount for m in facts.amounts):
            printed = ", ".join(f"{m.currency} {m.amount:.2f}" for m in facts.amounts)
            flags.append(RedFlag(
                code="QR_MISMATCH", severity="high",
                evidence=f"The amount in the QR code ({qr.get('currency') or ''} {qr_amount:.2f}) "
                         f"differs from the printed amount ({printed}).".replace("  ", " "),
                span_ids=_spans(facts, "amounts"),
            ))
    creditor = (qr.get("creditor") or {}).get("name")
    if creditor and facts.sender_name:
        if fuzz.token_set_ratio(normalise(creditor), normalise(facts.sender_name)) < QR_NAME_MATCH_THRESHOLD:
            flags.append(RedFlag(
                code="QR_MISMATCH", severity="warn",
                evidence=f'The QR code pays "{creditor}", but the letter is from "{facts.sender_name}".',
                span_ids=_spans(facts, "sender_name"),
            ))
    return flags


def check_unusual_channel(facts: LetterFacts, text: str, patterns: dict) -> list[RedFlag]:
    haystack = "\n".join(filter(None, [text, facts.demanded_action or "", " ".join(facts.stated_options)]))
    folded = haystack.casefold()
    flags = []
    for channel in patterns.get("unusual_payment_channels", []):
        hit = next((t for t in channel["terms"] if t.casefold() in folded), None)
        if hit:
            flags.append(RedFlag(
                code="URGENCY_PAYMENT_UNUSUAL_CHANNEL", severity="high",
                evidence=f'The letter asks for payment through an unusual channel: "…{_context(haystack, hit)}…"',
                span_ids=_spans(facts, "demanded_action"),
            ))
    return flags


def check_legal_basis(facts: LetterFacts, text: str, patterns: dict) -> list[RedFlag]:
    folded = text.casefold()
    flags = []
    for entry in patterns.get("legal_basis", []):
        cite = next((t for t in entry["cites_any"] if t.casefold() in folded), None)
        if cite and any(t.casefold() in folded for t in entry["situation_any"]):
            flags.append(RedFlag(
                code="LEGAL_BASIS_INCONSISTENT", severity="high",
                evidence=f'{entry["evidence"].strip()} On the letter: "…{_context(text, cite)}…"',
                source_url=entry.get("source_url"),
                span_ids=_spans(facts, "demanded_action", "deadline_text"),
            ))
    return flags


def check_remedy_notice(facts: LetterFacts, text: str, patterns: dict) -> list[RedFlag]:
    expected = {e["letter_type"] for e in patterns.get("remedy_notice_expected") or []}
    if facts.letter_type not in expected:
        return []
    folded = text.casefold()
    if any(term in folded for term in patterns.get("remedy_notice_terms", [])):
        return []
    return [RedFlag(
        code="NO_LEGAL_REMEDY_NOTICE", severity="warn",
        evidence="This kind of decision normally explains how to appeal. No such instructions were found on the letter.",
        span_ids=[],
    )]


def run_checks(
    facts: LetterFacts,
    text: str,
    qr: dict | None = None,
    authority: dict | None = None,
    patterns: dict | None = None,
) -> list[RedFlag]:
    """Run all checks. `text` is the OCR text; `authority` the matched directory entry, if any."""
    patterns = patterns if patterns is not None else load_patterns()
    flags = [
        *check_sender_in_directory(facts, authority, patterns),
        *check_contact_mismatch(facts, authority),
        *check_foreign_iban(facts, authority, qr, patterns),
        *check_qr_mismatch(facts, qr),
        *check_unusual_channel(facts, text, patterns),
        *check_legal_basis(facts, text, patterns),
        *check_remedy_notice(facts, text, patterns),
    ]
    return flags
