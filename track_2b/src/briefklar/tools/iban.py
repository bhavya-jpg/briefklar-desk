"""IBAN checksum and country (spec section 9.2)."""

from __future__ import annotations

from stdnum import iban as stdnum_iban

SWISS_IBAN_COUNTRIES = {"CH", "LI"}


def compact(iban: str) -> str:
    return "".join(iban.split()).upper()


def validate_iban(iban: str) -> dict:
    value = compact(iban or "")
    country = value[:2] if len(value) >= 2 and value[:2].isalpha() else None
    return {
        "iban": value,
        "valid": bool(value) and stdnum_iban.is_valid(value),
        "country": country,
        "swiss": country in SWISS_IBAN_COUNTRIES,
    }
