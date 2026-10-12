"""Baselines (spec 15.1).

B0 is real and runs anywhere: Tesseract text + regular expressions, no model.
B1-B3 need Apertus (and the reader/judge model) and therefore only run in live mode or from recorded
responses; without those they are reported as "not_run".
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from briefklar.pipeline.verify import _AMOUNT, _IBAN, _MONTHS, _amount_cents

NEXT_STEP_BY_TYPE = {
    "payment_order": "object", "reminder": "pay", "tax_assessment": "pay", "fine": "pay", "serafe_invoice": "pay",
    "invoice_qr": "pay", "permit_renewal": "apply", "school_notice": "reply", "continuation_notice": "contact_office",
    "premium_reduction": "no_action", "rent_increase": "no_action", "unknown": "unknown",
}

_TYPE_RULES = [
    ("payment_order", r"zahlungsbefehl|commandement de payer|precetto esecutivo"),
    ("continuation_notice", r"pfändungsankündigung|avis de saisie|avviso di pignoramento"),
    ("reminder", r"\bmahnung\b|\brappel\b|sollecito"),
    ("tax_assessment", r"veranlagungsverfügung|décision de taxation|decisione di tassazione"),
    ("premium_reduction", r"prämienverbilligung|réduction des primes|riduzione dei premi"),
    ("fine", r"ordnungsbusse|\bbusse\b|\bamende\b|\bmulta\b"),
    ("serafe_invoice", r"radio- und fernsehabgabe|redevance|serafe"),
    ("rent_increase", r"mietzinserhöhung|hausse de loyer|aumento della pigione"),
    ("permit_renewal", r"aufenthaltsbewilligung|permis de séjour|permesso di dimora"),
    ("school_notice", r"elternabend|réunion de parents|riunione dei genitori"),
    ("invoice_qr", r"\brechnung\b|\bfacture\b|\bfattura\b"),
]
_PERIOD = re.compile(r"(?:innert|binnen|dans les|entro)\s+(\d{1,3})\s+(?:tagen|jours|giorni)", re.I)
_UNTIL = re.compile(r"(?:\bbis\b|jusqu'au|entro il|\bam\b)\s+(?:spätestens\s+)?(\d{1,2})(?:\.|er|°)?\s+([a-zäéûô]+)\s+(\d{4})", re.I)
_DATE = re.compile(r"(\d{1,2})(?:\.|er|°)?\s+([A-Za-zäéûô]+)\s+(\d{4})")
_MONTH_INDEX = {name.casefold(): i + 1 for names in _MONTHS.values() for i, name in enumerate(names)}


def _parse(day: str, month: str, year: str) -> date | None:
    index = _MONTH_INDEX.get(month.casefold())
    try:
        return date(int(year), index, int(day)) if index else None
    except ValueError:
        return None


def b0_predict(ocr_text: str, delivered_on: date | None) -> dict:
    """Non-AI floor: keyword rules for the type, regexes for the fields, naive date arithmetic."""
    folded = ocr_text.casefold()
    letter_type = next((name for name, pattern in _TYPE_RULES if re.search(pattern, folded)), "unknown")
    dates = [d for d in (_parse(*m.groups()) for m in _DATE.finditer(ocr_text)) if d]
    amounts = [c for c in (_amount_cents(raw) for raw in _AMOUNT.findall(ocr_text)) if c]
    ibans = [re.sub(r"\s+", "", raw) for raw in _IBAN.findall(ocr_text.upper())]
    period = _PERIOD.search(ocr_text)
    until = _UNTIL.search(ocr_text)
    due = None
    if until:
        due = _parse(*until.groups())
    elif period:
        start = delivered_on or (dates[0] if dates else None)
        due = start + timedelta(days=int(period.group(1))) if start else None  # no Swiss counting rules
    facts = {
        "letter_date": dates[0].isoformat() if dates else None,
        "amount_due": {"amount": f"{max(amounts) / 100:.2f}"} if amounts else None,
        "iban": ibans[0] if ibans else None,
        "reference_numbers": re.findall(r"\bRF\d{2}[A-Z0-9]{4,21}\b", ocr_text.upper()),
        "deadline_period_value": int(period.group(1)) if period else None,
        "deadline_fixed_date": due.isoformat() if until and due else None,
    }
    return {"letter_type": letter_type, "facts": facts, "due_date": due.isoformat() if due else None,
            "next_step": NEXT_STEP_BY_TYPE[letter_type], "red_flags": [], "flagged": False}


# -- B1-B3: prompts for live runs --------------------------------------------------------------------

B1_PROMPT = "Translate this letter into {language}. Return only the translation."
B3_PROMPT = (
    "You read a Swiss official letter from its image. Explain it in {language} for the recipient. "
    "State by which exact date they must act (compute it yourself) and what they can do. "
    "If the letter looks suspicious, say so."
)
READER_PROMPT = """You are a resident who only has the text below. Do not use outside knowledge.
Q1: By which exact date must you act? Answer YYYY-MM-DD or "unknown".
Q2: What should you do next? Choose one: object, pay, apply, reply, contact_office, no_action, beware, unknown.
Return JSON {"date": ..., "next_step": ...}.
TEXT:
<<<TEXT>>>"""
FAITHFULNESS_PROMPT = """Given the letter text, the explainer card and one sentence, answer with JSON
{"verdict": "supported" | "not_supported" | "partially", "phrase": "<supporting phrase or empty>"}.
LETTER:
<<<LETTER>>>
CARD:
<<<CARD>>>
SENTENCE:
<<<SENTENCE>>>"""
