"""Deadline engine against hand-computed cases (spec section 17.2).

tests/data/deadline_cases.csv was worked out from the rules in section 9.1 without running the engine.
"""

import csv
from datetime import date
from pathlib import Path

import pytest

from briefklar.tools import deadline as engine
from briefklar.tools.deadline import betreibungsferien, compute_deadline

CASES = list(csv.DictReader((Path(__file__).parent / "data" / "deadline_cases.csv").open(encoding="utf-8")))


def _run(row: dict):
    return compute_deadline(
        rule_family=row["rule_family"],
        period_value=int(row["period_value"]) if row["period_value"] else None,
        period_unit=row["period_unit"] or None,
        start_event=row["start_event"],
        start_date=date.fromisoformat(row["start_date"]) if row["start_date"] else None,
        canton=row["canton"],
        today=date(2026, 10, 10),
    )


def test_at_least_thirty_hand_computed_cases():
    assert len(CASES) >= 30


@pytest.mark.parametrize("row", CASES, ids=[r["id"] for r in CASES])
def test_hand_computed_case(row):
    result = _run(row)
    expected = date.fromisoformat(row["expected_due_date"]) if row["expected_due_date"] else None
    assert result.due_date == expected, f"{row['note']}\ntrace: {result.trace}"
    assert result.needs_delivery_date is (row["expected_needs_delivery"] == "true")
    assert result.verified_rule is (row["expected_verified"] == "true"), result.trace
    assert result.trace, "every result explains itself"


def test_thursday_delivery_ends_on_sunday_and_moves_to_monday():
    result = compute_deadline("schkg", 10, "days", "delivery", date(2026, 10, 8), "BE", today=date(2026, 10, 10))
    assert result.due_date == date(2026, 10, 19)
    assert result.days_left == 9
    assert any("SchKG Art. 31" in step and "Sunday" in step for step in result.trace)


def test_holiday_in_one_canton_only_gives_different_dates():
    in_lu = compute_deadline("schkg", 10, "days", "delivery", date(2026, 5, 25), "LU")
    in_be = compute_deadline("schkg", 10, "days", "delivery", date(2026, 5, 25), "BE")
    assert in_lu.due_date != in_be.due_date


def test_missing_delivery_date_asks_for_it():
    result = compute_deadline("schkg", 10, "days", "delivery", None, "BE")
    assert result.needs_delivery_date and result.due_date is None and result.days_left is None


def test_window_edges_are_inclusive_as_encoded():
    windows = {label: (first, last) for first, last, label in betreibungsferien(2026)}
    assert windows["Easter"] == (date(2026, 3, 29), date(2026, 4, 12))
    assert windows["15-31 July"] == (date(2026, 7, 15), date(2026, 7, 31))
    assert windows["Christmas"] == (date(2026, 12, 18), date(2027, 1, 1))


def test_no_rule_family_gives_no_date():
    assert compute_deadline("none", None, None, None, None, "BE").due_date is None


@pytest.mark.source_required
def test_betreibungsferien_bounds_confirmed_against_official_source():
    assert engine.BETREIBUNGSFERIEN_BOUNDS_VERIFIED, (
        "TODO(source): confirm the inclusive bounds of the SchKG Art. 56 windows, then set "
        "BETREIBUNGSFERIEN_BOUNDS_VERIFIED = True in tools/deadline.py"
    )


@pytest.mark.source_required
def test_generic_admin_counting_confirmed():
    assert engine.GENERIC_ADMIN_VERIFIED, (
        "TODO(source): confirm start-day and roll-over counting for administrative deadlines in the "
        "demo canton, then set GENERIC_ADMIN_VERIFIED = True in tools/deadline.py"
    )
