"""Client-language strings, localised dates and language quality lights."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from functools import lru_cache

import yaml
from babel.dates import format_date

from briefklar.config import KNOWLEDGE_DIR

DUE_DATE_TOKEN = "[[DUE_DATE]]"


@lru_cache
def _data() -> dict:
    return yaml.safe_load((KNOWLEDGE_DIR / "i18n.yaml").read_text(encoding="utf-8"))


def languages() -> dict[str, dict]:
    return _data()["languages"]


def t(key: str, lang: str, **params: str) -> str:
    entry = _data()["strings"][key]
    text = entry.get(lang) or entry["en"]
    return text.format(**params) if params else text


def strings_for(lang: str) -> dict[str, str]:
    return {key: entry.get(lang) or entry["en"] for key, entry in _data()["strings"].items()}


def format_long_date(d: date, lang: str) -> str:
    """Date with weekday, e.g. "Monday 19 October 2026", in the given language."""
    locale = languages().get(lang, {}).get("babel", "en_GB")
    try:
        return format_date(d, format="full", locale=locale)
    except Exception:  # unknown locale data: fall back to an unambiguous form
        return f"{d:%A} {d.day} {d:%B %Y}"


def format_short_date(d: date, lang: str = "en") -> str:
    locale = languages().get(lang, {}).get("babel", "en_GB")
    try:
        return format_date(d, format="EEE d MMM y", locale=locale)
    except Exception:
        return f"{d:%a} {d.day} {d:%b %Y}"


def format_money(amount: Decimal, currency: str = "CHF") -> str:
    whole, _, cents = f"{amount:.2f}".partition(".")
    groups = []
    while len(whole) > 3:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    groups.insert(0, whole)
    return f"{currency} {'’'.join(groups)}.{cents}"


@lru_cache
def language_lights() -> dict:
    return json.loads((KNOWLEDGE_DIR / "language_lights.json").read_text(encoding="utf-8"))


def chrf_threshold(lang: str) -> float:
    thresholds = language_lights()["thresholds"]["low_confidence_chrf"]
    return float(thresholds.get(lang, thresholds["default"]))
