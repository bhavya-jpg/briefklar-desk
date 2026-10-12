"""Printouts: client handout, German case note, reply letter. HTML (Jinja2) to PDF (WeasyPrint).

Fonts are loaded from local files only. No URL outside the font directory is ever fetched.
"""

from __future__ import annotations

import re
from datetime import date
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from briefklar import i18n
from briefklar.config import PROJECT_DIR, get_settings
from briefklar.models import Case, ReplyDraft
from briefklar.pipeline.explain import render_explanation
from briefklar.present import LETTER_TYPE_LABELS, creditor_totals, refresh_days_left

TEMPLATES = Path(__file__).parent / "templates"
_env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]))

_FONT_FILE = re.compile(r"^(?P<family>.+?)-(?P<subset>[a-z-]+?)-(?P<weight>\d{3})-normal\.woff2$")
# Script-specific faces first would hide Latin digits; Latin UI face first, then the script faces.
_FAMILY_ORDER = ("inter-tight", "noto-sans", "noto-sans-arabic", "noto-sans-ethiopic", "noto-sans-tamil", "jetbrains-mono")


def font_dir() -> Path | None:
    settings = get_settings()
    for candidate in (settings.static_dir / "fonts", PROJECT_DIR / "frontend" / "static" / "fonts",
                      Path("/usr/share/fonts/briefklar")):
        if candidate.is_dir() and any(candidate.glob("*.woff2")):
            return candidate
    return None


@lru_cache
def font_faces(base_url: str | None = None) -> tuple[str, str]:
    """(@font-face CSS, font-family stack) for the self-hosted fonts. One family per subset file, so
    glyph fallback across scripts works in print without unicode-range support."""
    directory = font_dir()
    if directory is None:
        return "", "sans-serif"
    rules, families = [], []
    files = sorted(directory.glob("*.woff2"))

    def rank(path: Path) -> tuple:
        match = _FONT_FILE.match(path.name)
        family = match["family"] if match else path.stem
        order = _FAMILY_ORDER.index(family) if family in _FAMILY_ORDER else len(_FAMILY_ORDER)
        subset = match["subset"] if match else ""
        return (order, 0 if subset == "latin" else 1, path.name)

    for path in sorted(files, key=rank):
        match = _FONT_FILE.match(path.name)
        if not match or match["family"] == "jetbrains-mono":
            continue
        name = f"bk-{match['family']}-{match['subset']}"
        url = f"{base_url.rstrip('/')}/{path.name}" if base_url else path.resolve().as_uri()
        rules.append(f'@font-face{{font-family:"{name}";font-weight:{match["weight"]};src:url("{url}") format("woff2")}}')
        if name not in families:
            families.append(name)
    stack = ", ".join(f'"{f}"' for f in families) + ", sans-serif"
    return "\n".join(rules), stack


def _html_to_pdf(html: str) -> bytes:
    from weasyprint import HTML
    from weasyprint.urls import URLFetcher

    # Local files and data URLs only: a printout can never trigger a network request.
    fetcher = URLFetcher(allowed_protocols=("file", "data"))
    return HTML(string=html, url_fetcher=fetcher, base_url=str(TEMPLATES)).write_pdf()


def _context(font_base_url: str | None) -> dict:
    css, stack = font_faces(font_base_url)
    return {"font_css": css, "font_stack": stack}


# -- handout -------------------------------------------------------------------------------------


def handout_html(case: Case, today: date, font_base_url: str | None = None) -> str:
    refresh_days_left(case, today)
    lang = case.client_language
    by_id = {l.id: l for l in case.letters}
    ordered = [by_id[i] for i in case.order if i in by_id] or list(case.letters)
    replied = {r.letter_id for r in case.replies}
    items, dates = [], []
    for number, letter in enumerate((l for l in ordered if l.status == "done" and l.explanation), start=1):
        deadline = letter.verification.deadline if letter.verification else None
        explanation = render_explanation(letter.explanation, deadline)
        if deadline and deadline.due_date:
            when = i18n.format_long_date(deadline.due_date, lang)
            dates.append((deadline.due_date, number, when))
        elif deadline and deadline.needs_delivery_date:
            when = i18n.t("date_needed", lang)
        else:
            when = None
        items.append({
            "number": number,
            "what": " ".join(s.text for s in explanation.what_this_is[:3]),
            "want": " ".join(s.text for s in explanation.what_they_want[:2]),
            "when": when,
            "flagged": bool(letter.verification and letter.verification.red_flags),
            "replied": letter.id in replied,
            "done": i18n.t("handout_reply_prepared", lang),
            "low_confidence": explanation.low_confidence,
        })
    meta = i18n.languages()[lang]
    return _env.get_template("handout.html").render(
        **_context(font_base_url), lang=lang, dir=meta["dir"], s=i18n.strings_for(lang),
        s_de=i18n.strings_for("de"), items=items, dates=[d for d in sorted(dates) if d[0] >= today],
        today=i18n.format_long_date(today, lang),
    )


def handout_pdf(case: Case, today: date) -> bytes:
    return _html_to_pdf(handout_html(case, today))


# -- case note -----------------------------------------------------------------------------------


def case_note_html(case: Case, today: date, font_base_url: str | None = None) -> str:
    refresh_days_left(case, today)
    by_id = {l.id: l for l in case.letters}
    ordered = [by_id[i] for i in case.order if i in by_id] or list(case.letters)
    rows = []
    for number, letter in enumerate(ordered, start=1):
        if letter.status != "done" or not letter.facts or not letter.verification:
            rows.append({"number": number, "failed": True, "error": letter.error or letter.status})
            continue
        facts, verification = letter.facts, letter.verification
        deadline = verification.deadline
        rows.append({
            "number": number,
            "type": LETTER_TYPE_LABELS[facts.letter_type][1],
            "sender": facts.sender_name,
            "creditor": facts.creditor_name,
            "references": facts.reference_numbers,
            "amount": i18n.format_money(facts.amount_due.amount, facts.amount_due.currency) if facts.amount_due else None,
            "letter_date": i18n.format_short_date(facts.letter_date, "de") if facts.letter_date else None,
            "due": i18n.format_long_date(deadline.due_date, "de") if deadline and deadline.due_date else None,
            "needs_delivery": bool(deadline and deadline.needs_delivery_date),
            "delivery": i18n.format_short_date(letter.delivery_date, "de") if letter.delivery_date else None,
            "trace": deadline.trace if deadline else [],
            "unverified": bool(deadline and not deadline.verified_rule),
            "flags": verification.red_flags,
            "checks": {k: v for k, v in verification.field_checks.items() if v != "match"},
            "low_confidence": bool(letter.explanation and letter.explanation.low_confidence),
            "replies": [r for r in case.replies if r.letter_id == letter.id],
        })
    threads = [
        {"numbers": [n for n, l in enumerate(ordered, start=1) if l.id in t.letter_ids], "reason": t.reason,
         "confirmed": t.confirmed}
        for t in case.threads if not t.rejected
    ]
    return _env.get_template("case_note.html").render(
        **_context(font_base_url), case=case, rows=rows, threads=threads, totals=creditor_totals(case),
        today=i18n.format_long_date(today, "de"), language=i18n.languages()[case.client_language],
        disclaimer=i18n.t("disclaimer", "de"),
    )


def case_note_pdf(case: Case, today: date) -> bytes:
    return _html_to_pdf(case_note_html(case, today))


# -- reply ---------------------------------------------------------------------------------------


def reply_html(reply: ReplyDraft, font_base_url: str | None = None) -> str:
    return _env.get_template("reply.html").render(**_context(font_base_url), reply=reply)


def reply_pdf(reply: ReplyDraft) -> bytes:
    return _html_to_pdf(reply_html(reply))
