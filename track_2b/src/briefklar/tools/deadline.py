"""Deterministic Swiss deadline engine (spec section 9.1).

Dates are never computed by the model. Verified rules exist for `schkg` only:

- SchKG Art. 31: the day a period starts is not counted; a period ending on a Saturday, Sunday or
  state-recognised public holiday ends on the next working day; month periods end on the day with the
  same number, or on the last day of the month if that day does not exist.
- SchKG Art. 56: debt-enforcement holidays (Betreibungsferien): seven days before and after Easter and
  Christmas, and 15-31 July.
- SchKG Art. 63: a period that ends during the holidays is extended to the third day after they end;
  Saturdays, Sundays and public holidays are not counted in those three days.

Source for all three: https://law.ch/lawinfo/fristen/schuldbetreibungs-und-konkursrecht-schkg/gesetzliche-grundlagen/
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from functools import lru_cache

import holidays as holidays_lib
from dateutil.easter import easter

from briefklar.models import DeadlineResult

# TODO(source): confirm the inclusive bounds of "seven days before and after" Easter and Christmas
# (SchKG Art. 56) against an official source. Encoded as: Easter Sunday -7..+7 and 25 Dec -7..+7
# (18 Dec - 1 Jan), both ends included. Until confirmed, any deadline that touches a window is
# returned with verified_rule=False.
BETREIBUNGSFERIEN_BOUNDS_VERIFIED = False
EASTER_DAYS_BEFORE = 7
EASTER_DAYS_AFTER = 7
CHRISTMAS_DAYS_BEFORE = 7
CHRISTMAS_DAYS_AFTER = 7
JULY_WINDOW = (15, 31)
ART_63_EXTENSION_DAYS = 3

# TODO(source): generic_admin counting (start day not counted, weekend/holiday roll-over) must be
# confirmed against the procedural law of the demo canton before it is shown as verified.
GENERIC_ADMIN_VERIFIED = False


def fmt(d: date) -> str:
    return f"{d:%a} {d.day} {d:%b %Y}"


@lru_cache(maxsize=512)
def _holiday_calendar(canton: str, year: int) -> holidays_lib.HolidayBase:
    # TODO(source): confirm the holiday set against the canton's official list for the demo canton.
    return holidays_lib.Switzerland(subdiv=canton, years=year)


def holiday_name(d: date, canton: str) -> str | None:
    return _holiday_calendar(canton, d.year).get(d)


def is_working_day(d: date, canton: str) -> bool:
    return d.weekday() < 5 and holiday_name(d, canton) is None


def betreibungsferien(year: int) -> list[tuple[date, date, str]]:
    """Inclusive (first, last, label) windows that begin in `year` (SchKG Art. 56)."""
    easter_sunday = easter(year)
    christmas = date(year, 12, 25)
    return [
        (easter_sunday - timedelta(days=EASTER_DAYS_BEFORE),
         easter_sunday + timedelta(days=EASTER_DAYS_AFTER), "Easter"),
        (date(year, 7, JULY_WINDOW[0]), date(year, 7, JULY_WINDOW[1]), "15-31 July"),
        (christmas - timedelta(days=CHRISTMAS_DAYS_BEFORE),
         christmas + timedelta(days=CHRISTMAS_DAYS_AFTER), "Christmas"),
    ]


def window_containing(d: date) -> tuple[date, date, str] | None:
    for year in (d.year - 1, d.year):
        for first, last, label in betreibungsferien(year):
            if first <= d <= last:
                return first, last, label
    return None


def add_period(start: date, value: int, unit: str) -> date:
    """Art. 31: days are counted from the day after `start`; months land on the same day number."""
    if unit == "days":
        return start + timedelta(days=value)
    if unit == "months":
        month_index = start.month - 1 + value
        year, month = start.year + month_index // 12, month_index % 12 + 1
        return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))
    raise ValueError(f"unknown period unit: {unit!r}")


def _roll_to_working_day(end: date, canton: str, trace: list[str], cite: str) -> date:
    while not is_working_day(end, canton):
        reason = holiday_name(end, canton) or f"{end:%A}"
        nxt = end + timedelta(days=1)
        while not is_working_day(nxt, canton):
            nxt += timedelta(days=1)
        trace.append(f"{fmt(end)} is not a working day ({reason}) → moved to {fmt(nxt)} ({cite})")
        end = nxt
    return end


def compute_deadline(
    rule_family: str,
    period_value: int | None,
    period_unit: str | None,
    start_event: str | None,
    start_date: date | None,
    canton: str,
    today: date | None = None,
) -> DeadlineResult:
    """Return the last day to act, with a human-readable trace.

    `start_date` is the delivery date, the letter date or the fixed date, depending on `start_event`.
    """
    today = today or date.today()

    def result(due: date | None, trace: list[str], verified: bool, needs_delivery: bool = False) -> DeadlineResult:
        return DeadlineResult(
            due_date=due,
            days_left=(due - today).days if due else None,
            needs_delivery_date=needs_delivery,
            rule_family=rule_family,
            trace=trace,
            verified_rule=verified,
            period_value=period_value,
            period_unit=period_unit,  # type: ignore[arg-type]
            start_event=start_event,  # type: ignore[arg-type]
            start_date=start_date,
        )

    if rule_family == "none" or start_event is None:
        return result(None, ["No deadline rule applies to this letter."], True)

    if start_date is None:
        if start_event == "delivery":
            return result(
                None,
                ["The period runs from the day the letter was delivered. Delivery date needed."],
                rule_family == "schkg",
                needs_delivery=True,
            )
        return result(None, [f"The {start_event.replace('_', ' ')} is missing, so no date can be computed."], False)

    trace: list[str] = []
    verified = True

    if start_event == "fixed_date":
        end = start_date
        trace.append(f"Date printed on the letter: {fmt(end)}")
    else:
        if period_value is None or period_unit is None:
            return result(None, ["The letter states no period, so no date can be computed."], False)
        label = "Delivered" if start_event == "delivery" else "Letter dated"
        trace.append(f"{label} {fmt(start_date)}")
        end = add_period(start_date, period_value, period_unit)
        counting = "start day not counted" if period_unit == "days" else "same day number, or last day of the month"
        cite = {"schkg": "SchKG Art. 31", "generic_admin": "rule unverified", "contract": "period stated in the letter"}[
            rule_family
        ]
        trace.append(f"+{period_value} {period_unit} ({counting}; {cite}) → {fmt(end)}")

    if rule_family == "contract":
        trace.append("Contractual date: no roll-over applied.")
        return result(end, trace, True)

    if rule_family == "generic_admin":
        end = _roll_to_working_day(end, canton, trace, "rule unverified")
        trace.append(
            f"Rule unverified: check the counting against the procedural law of canton {canton} (source required)."
        )
        return result(end, trace, GENERIC_ADMIN_VERIFIED)

    if rule_family != "schkg":
        raise ValueError(f"unknown rule family: {rule_family!r}")

    window = window_containing(end)
    if window:
        first, last, label = window
        trace.append(
            f"{fmt(end)} falls in the debt-enforcement holidays ({label}: {fmt(first)} – {fmt(last)}, SchKG Art. 56)"
        )
        cursor, counted = last, 0
        while counted < ART_63_EXTENSION_DAYS:
            cursor += timedelta(days=1)
            if is_working_day(cursor, canton):
                counted += 1
        end = cursor
        trace.append(
            f"Extended to the third working day after the holidays end → {fmt(end)} "
            "(SchKG Art. 63; Saturdays, Sundays and public holidays not counted)"
        )
        if not BETREIBUNGSFERIEN_BOUNDS_VERIFIED:
            verified = False
            trace.append("Holiday window bounds not yet confirmed against an official source: check manually.")
    else:
        end = _roll_to_working_day(end, canton, trace, "SchKG Art. 31")
        if window_containing(end):
            # The spec's algorithm applies Art. 63 to the raw end only. How Art. 31 and Art. 63 combine
            # when the roll-over lands inside the holidays is not sourced. TODO(source)
            verified = False
            trace.append(
                "The moved date falls in the debt-enforcement holidays. How Art. 31 and Art. 63 combine "
                "here is not confirmed: check manually."
            )

    return result(end, trace, verified)
