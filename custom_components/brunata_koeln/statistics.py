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
from .models import MediumReadings, daily_sources
from .parser import MEDIA


async def import_history(hass, entry, data):
    """Reconcile the previous and current year, chaining their cumulative sums."""
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
        # The previous billing period is imported first into the same IDs. Its
        # closing sum is passed on directly: Recorder writes asynchronously, so
        # reading it back in the same refresh could still return no rows.
        previous = {
            "": (readings.previous, monthly_statistics),
            "_daily_average": (
                daily_sources(
                    MediumReadings(medium, readings.previous), as_of=now.date()
                ),
                daily_builder,
            ),
        }
        for suffix, source, builder, label in series:
            baseline = None
            prior_source, prior_builder = previous.get(suffix, ((), None))
            if prior_source:
                baseline = await _import_series(
                    hass,
                    entry,
                    medium,
                    suffix,
                    prior_source,
                    prior_builder,
                    label,
                    year - 1,
                    berlin,
                )
            await _import_series(
                hass,
                entry,
                medium,
                suffix,
                source,
                builder,
                label,
                year,
                berlin,
                baseline=baseline,
            )


async def _import_series(
    hass, entry, medium, suffix, source, builder, label, year, berlin, baseline=None
):
    """Import one year and return its closing sum, or None without rows."""
    rows = builder(source, year)
    if not rows:
        return None
    statistic_id = f"{DOMAIN}:{entry.unique_id}_{MEDIA[medium]}{suffix}"
    if baseline is None:
        baseline = await _stored_baseline(hass, statistic_id, year, berlin)
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
    return rows[-1]["sum"]


async def _stored_baseline(hass, statistic_id, year, berlin):
    """Return the stored closing sum of the year before ``year``, else zero."""
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
    return previous_rows[-1]["sum"] if previous_rows else 0.0
