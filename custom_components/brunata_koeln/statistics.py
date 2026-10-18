"""Import external consumption statistics separately from entity recordings."""

from datetime import UTC, datetime
from functools import partial
from zoneinfo import ZoneInfo

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    statistics_during_period,
)

from .const import DOMAIN
from .history import daily_average_statistics, monthly_statistics
from .models import daily_sources
from .parser import MEDIA


async def import_history(hass, entry, data):
    """Reconcile current-year readings, retaining the previous year's baseline."""
    berlin = ZoneInfo("Europe/Berlin")
    now = datetime.now(berlin)
    year = now.year
    daily_builder = partial(daily_average_statistics, as_of=now)
    for medium, readings in data.items():
        series = (
            ("", readings.readings, monthly_statistics, "monthly consumption"),
            (
                "_daily_average",
                daily_sources(readings, as_of=now.date()),
                daily_builder,
                "average daily distribution",
            ),
            (
                "_property_average",
                readings.property_average,
                monthly_statistics,
                "property average monthly consumption",
            ),
            (
                "_property_daily_average",
                daily_sources(readings, True, as_of=now.date()),
                daily_builder,
                "property average daily distribution",
            ),
        )
        for suffix, source, builder, label in series:
            await _import_series(
                hass, entry, medium, suffix, source, builder, label, year, berlin
            )


async def _import_series(
    hass, entry, medium, suffix, source, builder, label, year, berlin
):
    rows = builder(source, year)
    if not rows:
        return
    statistic_id = f"{DOMAIN}:{entry.unique_id}_{MEDIA[medium]}{suffix}"
    previous = await get_instance(hass).async_add_executor_job(
        partial(
            statistics_during_period,
            hass,
            datetime(year - 1, 1, 1, tzinfo=berlin).astimezone(UTC),
            datetime(year, 1, 1, tzinfo=berlin).astimezone(UTC),
            {statistic_id},
            "hour",
            None,
            {"sum"},
        )
    )
    previous_rows = previous.get(statistic_id, [])
    baseline = previous_rows[-1]["sum"] if previous_rows else 0.0
    for row in rows:
        row["sum"] += baseline
        row["state"] += baseline
    unit = source[0].unit
    async_add_external_statistics(
        hass,
        {
            "statistic_id": statistic_id,
            "source": DOMAIN,
            "name": f"BRUNATA {MEDIA[medium]} {label}",
            "unit_of_measurement": unit,
            "unit_class": "energy" if unit == "kWh" else "volume",
            "mean_type": StatisticMeanType.NONE,
            "has_sum": True,
        },
        rows,
    )
