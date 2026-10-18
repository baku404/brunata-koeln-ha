"""Portal-independent monthly consumption models."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class MonthlyReading:
    """A reported monthly consumption value, never a meter index."""

    month: date
    value: float
    unit: str


@dataclass(frozen=True)
class MediumReadings:
    """Readings for one medium in the portal's selected tenancy and period."""

    medium: str
    readings: tuple[MonthlyReading, ...]

    property_average: tuple[MonthlyReading, ...] = ()

    forecasts: tuple[MonthlyReading, ...] = ()
    property_forecasts: tuple[MonthlyReading, ...] = ()

    @property
    def latest(self) -> MonthlyReading | None:
        """Return the most recent reported month."""
        return self.readings[-1] if self.readings else None


def daily_sources(
    data: MediumReadings, property_basis: bool = False, *, as_of: date | None = None
):
    """Actual values replace forecasts for the same source month."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    cutoff = (as_of or datetime.now(ZoneInfo("Europe/Berlin")).date()).replace(day=1)
    forecasts = data.property_forecasts if property_basis else data.forecasts
    actual = data.property_average if property_basis else data.readings
    merged = {x.month: x for x in forecasts if x.month <= cutoff}
    merged.update({x.month: x for x in actual if x.month < cutoff})
    return tuple(merged[key] for key in sorted(merged))
