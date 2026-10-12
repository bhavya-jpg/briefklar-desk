"""The case as the UI and the printouts see it: rendered dates, current days-left, creditor totals."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from briefklar import i18n
from briefklar.models import Case, Letter
from briefklar.pipeline import reply as reply_pass
from briefklar.pipeline.explain import render_explanation
from briefklar.tools.authority import normalise

LETTER_TYPE_LABELS = {
    "payment_order": ("Payment order", "Zahlungsbefehl"),
    "reminder": ("Reminder", "Mahnung"),
    "tax_assessment": ("Tax assessment", "Steuerveranlagung"),
    "premium_reduction": ("Premium reduction decision", "Verfügung Prämienverbilligung"),
    "fine": ("Fine", "Busse"),
    "serafe_invoice": ("Serafe invoice", "Serafe-Rechnung"),
    "rent_increase": ("Rent increase", "Mietzinserhöhung"),
    "permit_renewal": ("Residence permit renewal", "Verlängerung Aufenthaltsbewilligung"),
    "school_notice": ("School notice", "Mitteilung der Schule"),
    "invoice_qr": ("Invoice", "Rechnung"),
    "continuation_notice": ("Continuation notice", "Fortsetzung der Betreibung"),
    "unknown": ("Letter", "Brief"),
}


def refresh_days_left(case: Case, today: date) -> None:
    for letter in case.letters:
        deadline = letter.verification.deadline if letter.verification else None
        if deadline and deadline.due_date:
            deadline.days_left = (deadline.due_date - today).days


def creditor_totals(case: Case) -> list[dict]:
    """Open total per creditor: per thread only the most recent demand counts; flagged letters are left out."""
    by_id = {l.id: l for l in case.letters if l.status == "done" and l.facts}
    threaded: set[str] = set()
    claims: list[Letter] = []
    for thread in case.threads:
        if not thread.confirmed or thread.rejected:
            continue
        members = [by_id[i] for i in thread.letter_ids if i in by_id and by_id[i].facts.amount_due]
        threaded.update(thread.letter_ids)
        if members:
            claims.append(max(members, key=lambda l: (l.facts.letter_date or date.min, l.facts.amount_due.amount)))
    claims += [l for l in by_id.values() if l.id not in threaded and l.facts.amount_due]

    totals: dict[str, dict] = {}
    for letter in claims:
        if letter.verification and letter.verification.red_flags:
            continue
        facts = letter.facts
        name = facts.creditor_name or facts.sender_name or "Unknown"
        key = (normalise(name), facts.amount_due.currency)
        entry = totals.setdefault(str(key), {"creditor": name, "currency": facts.amount_due.currency,
                                             "total": Decimal("0"), "letter_ids": []})
        entry["total"] += facts.amount_due.amount
        entry["letter_ids"].append(letter.id)
    out = sorted(totals.values(), key=lambda e: (-e["total"], e["creditor"]))
    for entry in out:
        entry["display"] = i18n.format_money(entry["total"], entry["currency"])
        entry["total"] = f"{entry['total']:.2f}"
    return out


def present_letter(case: Case, letter: Letter) -> dict:
    data = letter.model_dump(mode="json")
    deadline = letter.verification.deadline if letter.verification else None
    for key in ("explanation", "explanation_de"):
        explanation = getattr(letter, key)
        if explanation is not None:
            data[key] = render_explanation(explanation, deadline).model_dump(mode="json")
    data["pages"] = [
        {"id": p.id, "width": p.width, "height": p.height, "url": f"/api/cases/{case.id}/pages/{p.id}.jpg"}
        for p in case.pages if p.id in letter.page_ids
    ]
    if letter.facts:
        en, de = LETTER_TYPE_LABELS[letter.facts.letter_type]
        data["type_label"], data["type_label_de"] = en, de
        flagged = bool(letter.verification and letter.verification.red_flags)
        # no reply is drafted to the sender of a letter with warning signs
        data["reply_templates"] = [] if flagged else reply_pass.available_templates(letter.facts)
        if letter.facts.letter_date:
            data["letter_date_display"] = i18n.format_short_date(letter.facts.letter_date, "en")
        if letter.facts.amount_due:
            data["amount_display"] = i18n.format_money(letter.facts.amount_due.amount, letter.facts.amount_due.currency)
    if deadline and deadline.due_date:
        data["due_display"] = i18n.format_short_date(deadline.due_date, "en")
        data["due_display_client"] = i18n.format_long_date(deadline.due_date, case.client_language)
    return data


def present_case(case: Case, today: date) -> dict:
    refresh_days_left(case, today)
    data = case.model_dump(mode="json", exclude={"letters", "pages"})
    data["today"] = today.isoformat()
    data["today_display"] = i18n.format_short_date(today, "en")
    data["letters"] = [present_letter(case, letter) for letter in case.letters]
    data["unassigned_pages"] = [
        {"id": p.id, "url": f"/api/cases/{case.id}/pages/{p.id}.jpg", "filename": p.filename}
        for p in case.pages if not any(p.id in l.page_ids for l in case.letters)
    ]
    data["creditor_totals"] = creditor_totals(case)
    data["language"] = {"code": case.client_language, **i18n.languages()[case.client_language]}
    data["strings"] = i18n.strings_for(case.client_language)
    data["strings_de"] = i18n.strings_for("de")
    return data
