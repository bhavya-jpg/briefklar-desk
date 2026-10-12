"""Pydantic models (spec section 10). Fields beyond the spec are marked `# extension`."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, get_args

from pydantic import BaseModel, Field

LangCode = Literal["de", "fr", "it", "en", "sq", "pt", "bcs", "es", "ta", "ti", "ar", "uk", "tr"]
SourceLang = Literal["de", "fr", "it"]
CantonCode = Literal[
    "AG", "AI", "AR", "BE", "BL", "BS", "FR", "GE", "GL", "GR", "JU", "LU", "NE",
    "NW", "OW", "SG", "SH", "SO", "SZ", "TG", "TI", "UR", "VD", "VS", "ZG", "ZH",
]
LetterType = Literal[
    "payment_order", "reminder", "tax_assessment", "premium_reduction",
    "fine", "serafe_invoice", "rent_increase", "permit_renewal",
    "school_notice", "invoice_qr", "continuation_notice", "unknown",
]
RuleFamily = Literal["schkg", "generic_admin", "contract", "none"]
PeriodUnit = Literal["days", "months"]
StartEvent = Literal["delivery", "letter_date", "fixed_date"]

LANG_CODES: tuple[str, ...] = get_args(LangCode)
CANTON_CODES: tuple[str, ...] = get_args(CantonCode)
LETTER_TYPES: tuple[str, ...] = get_args(LetterType)

# Which deadline rules apply to which letter type. Not a legal period: only the family of counting rules.
RULE_FAMILY_BY_TYPE: dict[str, RuleFamily] = {
    "payment_order": "schkg",
    "continuation_notice": "schkg",
    "reminder": "contract",
    "invoice_qr": "contract",
    "serafe_invoice": "contract",
    "rent_increase": "contract",
    "tax_assessment": "generic_admin",
    "premium_reduction": "generic_admin",
    "fine": "generic_admin",
    "permit_renewal": "generic_admin",
    "school_notice": "generic_admin",
    "unknown": "generic_admin",
}


class Evidence(BaseModel):
    id: str  # "e1", "e2", ...
    text: str  # exact phrase from the letter
    page: int = 0
    # Normalised (x0, y0, x1, y1) in 0..1 of the page; filled by aligning text to OCR word boxes.
    bbox: tuple[float, float, float, float] | None = None


class Money(BaseModel):
    amount: Decimal
    currency: Literal["CHF", "EUR"] = "CHF"


class LetterFacts(BaseModel):
    letter_type: LetterType
    source_language: SourceLang
    sender_name: str | None = None
    sender_address: str | None = None
    sender_contact: str | None = None
    recipient_name: str | None = None
    recipient_address: str | None = None  # extension: needed to address a reply
    creditor_name: str | None = None  # extension: creditor named in a payment order, if not the sender
    letter_date: date | None = None
    reference_numbers: list[str] = []
    amounts: list[Money] = []
    amount_due: Money | None = None  # extension: the total the letter asks the recipient to pay
    iban: str | None = None
    demanded_action: str | None = None
    deadline_text: str | None = None
    deadline_period_value: int | None = None
    deadline_period_unit: PeriodUnit | None = None
    deadline_start_event: StartEvent | None = None
    deadline_fixed_date: date | None = None
    stated_options: list[str] = []
    evidence: dict[str, list[str]] = {}  # field name -> evidence ids
    evidence_items: list[Evidence] = []


class DeadlineResult(BaseModel):
    due_date: date | None
    days_left: int | None
    needs_delivery_date: bool
    rule_family: str
    trace: list[str]  # human-readable steps with rule citations
    verified_rule: bool  # False -> amber "rule unverified"
    # extension: inputs kept so the deadline can be recomputed when the delivery date arrives
    period_value: int | None = None
    period_unit: PeriodUnit | None = None
    start_event: StartEvent | None = None
    start_date: date | None = None


class RedFlag(BaseModel):
    code: str
    severity: Literal["warn", "high"]
    evidence: str
    span_ids: list[str] = []
    source_url: str | None = None  # extension: where a pattern comes from; shown as a link, never as text


class Verification(BaseModel):
    deadline: DeadlineResult | None = None
    iban_valid: bool | None = None
    iban_country: str | None = None
    qr: dict | None = None
    authority_id: str | None = None
    authority_contact: dict | None = None
    red_flags: list[RedFlag] = []
    field_checks: dict[str, Literal["match", "mismatch", "ocr_missing"]] = {}
    orchestrator_forced_tools: list[str] = []
    model_tool_calls: list[str] = []  # extension: tools the model called itself (reported in eval)


class Sentence(BaseModel):
    text: str
    support: list[str]  # evidence ids or "card:<id>"


EXPLANATION_SECTIONS = ("what_this_is", "what_they_want", "deadline", "what_you_can_do", "who_to_contact")


class Explanation(BaseModel):
    language: LangCode
    what_this_is: list[Sentence]
    what_they_want: list[Sentence]
    deadline: list[Sentence]
    what_you_can_do: list[Sentence]
    who_to_contact: list[Sentence]
    low_confidence: bool = False
    backtranslation_chrf: float | None = None
    failed_field_checks: list[str] = []  # extension: which of date/amount/sender did not survive back-translation

    def sentences(self) -> list[Sentence]:
        return [s for name in EXPLANATION_SECTIONS for s in getattr(self, name)]

    def text(self) -> str:
        return "\n".join(s.text for s in self.sentences())


class Thread(BaseModel):
    id: str
    letter_ids: list[str]
    reason: str
    confirmed: bool  # deterministic linker agreed
    origin: Literal["model", "linker", "both", "counsellor"] = "both"  # extension
    rejected: bool = False  # extension: counsellor rejected a dashed link


class ReplyDraft(BaseModel):
    id: str = ""  # extension
    letter_id: str = ""  # extension
    template_id: str
    language: SourceLang
    slots: dict[str, str]
    slot_sources: dict[str, list[str]]
    needs_review: list[str]  # slots drafted by the model
    rendered_text: str
    missing: list[str] = []  # extension: required slots still empty or awaiting an official source


class OcrWord(BaseModel):
    text: str
    bbox: tuple[float, float, float, float]  # normalised
    line: int = 0


class Page(BaseModel):
    id: str
    filename: str
    sha256: str  # of the uploaded bytes; identifies the image in the replay key
    width: int = 0
    height: int = 0
    ocr_text: str = Field(default="", exclude=True)
    ocr_words: list[OcrWord] = Field(default=[], exclude=True)
    qr_payloads: list[str] = Field(default=[], exclude=True)
    source_language: SourceLang = "de"


class Letter(BaseModel):
    id: str
    page_ids: list[str]
    status: Literal["queued", "processing", "done", "failed", "skipped"] = "queued"
    stage: str | None = None
    error: str | None = None
    delivery_date: date | None = None
    facts: LetterFacts | None = None
    verification: Verification | None = None
    explanation: Explanation | None = None  # client language
    explanation_de: Explanation | None = None  # simple German twin
    priority_reason: str | None = None  # from the case pass; tooltip only
    label: str | None = None  # extension: e.g. demo letter id


class Case(BaseModel):
    id: str  # random, not tied to client identity
    created_at: datetime
    client_language: LangCode
    canton: CantonCode
    letters: list[Letter] = []
    threads: list[Thread] = []
    status: Literal["capturing", "processing", "ready", "closed"] = "capturing"
    # extensions
    pages: list[Page] = []
    order: list[str] = []  # letter ids, most urgent first (section 8.5)
    replies: list[ReplyDraft] = []
    today: date | None = None  # "as of" date for days-left; demo cases pin it
    client_name: str | None = None  # only if the counsellor types it
    demo: bool = False
    model_misses: int = 0  # links the linker found but the model did not propose
