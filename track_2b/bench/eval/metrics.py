"""Metrics for Swiss Letters Bench (spec 15.2). Pure functions, no model calls."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from itertools import combinations

FIELDS = ("sender_name", "recipient_name", "letter_date", "reference_numbers", "amount_due", "iban",
          "deadline_fixed_date", "deadline_period_value", "creditor_name")


def normalise(field: str, value) -> set[str]:
    """Normalised comparable values for one field: whitespace, case, CHF amounts to cents."""
    if value in (None, "", []):
        return set()
    if field == "amount_due":
        raw = value["amount"] if isinstance(value, dict) else value
        try:
            return {str(int(Decimal(str(raw)) * 100))}
        except InvalidOperation:
            return {str(raw)}
    if field == "reference_numbers":
        return {re.sub(r"[^A-Z0-9]", "", str(v).upper()) for v in value}
    if field == "iban":
        return {re.sub(r"\s+", "", str(value).upper())}
    return {re.sub(r"\s+", " ", str(value)).strip().casefold()}


def field_counts(predicted: dict, gold: dict) -> dict[str, tuple[int, int, int]]:
    """Per field: (true positives, false positives, false negatives)."""
    out = {}
    for field in FIELDS:
        p, g = normalise(field, predicted.get(field)), normalise(field, gold.get(field))
        out[field] = (len(p & g), len(p - g), len(g - p))
    return out


def f1(tp: int, fp: int, fn: int) -> float | None:
    if tp + fp + fn == 0:
        return None
    return round(2 * tp / (2 * tp + fp + fn), 4)


def ratio(hits: int, total: int) -> float | None:
    return round(hits / total, 4) if total else None


def precision_recall(tp: int, fp: int, fn: int) -> tuple[float | None, float | None]:
    return ratio(tp, tp + fp), ratio(tp, tp + fn)


def kendall_tau(predicted: list[str], gold: list[str]) -> float | None:
    """Kendall's tau between two orders of the same items. Items missing from `predicted` go last."""
    position = {item: i for i, item in enumerate(predicted)}
    items = [i for i in gold]
    if len(items) < 2:
        return None
    rank = [position.get(item, len(predicted)) for item in items]
    concordant = discordant = 0
    for a, b in combinations(range(len(items)), 2):
        if rank[a] < rank[b]:
            concordant += 1
        elif rank[a] > rank[b]:
            discordant += 1
    pairs = len(items) * (len(items) - 1) / 2
    return round((concordant - discordant) / pairs, 4)


def thread_pairs(threads: list[list[str]]) -> set[frozenset[str]]:
    return {frozenset(pair) for ids in threads for pair in combinations(sorted(ids), 2)}


def pairwise_counts(predicted: list[list[str]], gold: list[list[str]]) -> tuple[int, int, int]:
    p, g = thread_pairs(predicted), thread_pairs(gold)
    return len(p & g), len(p - g), len(g - p)
