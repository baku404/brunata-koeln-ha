"""Build deterministic monthly statistics without inventing daily profiles."""

from datetime import UTC, date, datetime, timedelta
from math import isfinite
from zoneinfo import ZoneInfo

from .models import MonthlyReading

BERLIN = ZoneInfo("Europe/Berlin")


def monthly_statistics(readings: tuple[MonthlyReading, ...], year: int):
    """Book each interval in its final hour; only month/year views are meaningful.

    Emit a zero baseline at each month's start, carried forward cumulatively.
    Stable timestamps make repeated imports and corrected sums overwrite safely.
    Stop at a gap: an unknown month must not silently become zero consumption.
    """
    by_month = {x.month: x for x in readings if x.month.year == year}
    if len(by_month) != sum(x.month.year == year for x in readings):
        raise ValueError("Duplicate history month")
    result = []
    total = 0.0
    unit = None
    for month in range(min((d.month for d in by_month), default=1), 13):
        reading = by_month.get(date(year, month, 1))
        if reading is None:
            break
        if not isfinite(reading.value) or reading.value < 0:
            raise ValueError("Invalid history consumption")
        if unit is not None and unit != reading.unit:
            raise ValueError("Mixed history units")
        unit = reading.unit
        start = datetime(year, month, 1, tzinfo=BERLIN).astimezone(UTC)
        end = datetime(
            year + (month == 12), month % 12 + 1, 1, tzinfo=BERLIN
        ).astimezone(UTC)
        result.append({"start": start, "state": total, "sum": total})
        total += reading.value
        result.append({"start": end - timedelta(hours=1), "state": total, "sum": total})
    return result


def daily_average_statistics(
    readings: tuple[MonthlyReading, ...], year: int, *, as_of: datetime | None = None
):
    """Distribute each actual monthly total equally over its calendar days.

    Days with 23 or 25 hours receive the same daily share. The allocation is
    booked in each day's last hour; this does not assert hourly measurements.
    """
    from calendar import monthrange

    validated = monthly_statistics(readings, year)
    included = {
        row["start"].astimezone(BERLIN).date().replace(day=1) for row in validated
    }
    selected = sorted(
        (x for x in readings if x.month in included), key=lambda x: x.month
    )
    result = []
    total = 0.0
    for reading in selected:
        days = monthrange(reading.month.year, reading.month.month)[1]
        local_now = as_of.astimezone(BERLIN) if as_of else None
        if local_now and reading.month > local_now.date().replace(day=1):
            continue
        last_day = (
            min(days, local_now.day)
            if local_now and reading.month == local_now.date().replace(day=1)
            else days
        )
        for day in range(1, last_day + 1):
            local = datetime(year, reading.month.month, day, tzinfo=BERLIN)
            start = local.astimezone(UTC)
            end = (local + timedelta(days=1)).astimezone(UTC)
            before = total + reading.value * (day - 1) / days
            after = total + reading.value * day / days
            result.append({"start": start, "state": before, "sum": before})
            end_slot = end - timedelta(hours=1)
            if local_now:
                end_slot = start if local.date() == local_now.date() else end_slot
            if end_slot == start:
                result[-1] = {"start": start, "state": after, "sum": after}
            else:
                result.append({"start": end_slot, "state": after, "sum": after})
        total += reading.value
    return result
