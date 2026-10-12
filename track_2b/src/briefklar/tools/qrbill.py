"""Parse the payload of a Swiss QR-bill (the `SPC` QR code).

Implements payload version 0200: one data element per line, in fixed order.
TODO(source): cite the exact edition of the Swiss Payment Standards "Swiss Implementation Guidelines
QR-bill" this was checked against. Until then the layout is verified only by round-trip against the
`qrbill` library (tests/test_tools.py).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

SPC_HEADER = "SPC"

_ADDRESS_FIELDS = ("address_type", "name", "line1", "line2", "postal_code", "town", "country")


def is_qr_bill(payload: str) -> bool:
    return payload.lstrip().startswith(SPC_HEADER)


def _address(lines: list[str], start: int) -> dict | None:
    block = dict(zip(_ADDRESS_FIELDS, lines[start : start + 7]))
    return block if block.get("name") else None


def parse_qr_bill(payload: str) -> dict:
    lines = [line.strip() for line in payload.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    if not lines or lines[0] != SPC_HEADER:
        raise ValueError("not a Swiss QR-bill payload (missing SPC header)")
    lines += [""] * (34 - len(lines))
    try:
        amount = Decimal(lines[18]) if lines[18] else None
    except InvalidOperation as exc:
        raise ValueError(f"invalid amount in QR-bill: {lines[18]!r}") from exc
    return {
        "version": lines[1],
        "iban": lines[3].replace(" ", "").upper(),
        "creditor": _address(lines, 4),
        "ultimate_creditor": _address(lines, 11),
        "amount": str(amount) if amount is not None else None,
        "currency": lines[19] or None,
        "debtor": _address(lines, 20),
        "reference_type": lines[27] or None,
        "reference": lines[28].replace(" ", "") or None,
        "message": lines[29] or None,
        "trailer": lines[30] or None,
    }
