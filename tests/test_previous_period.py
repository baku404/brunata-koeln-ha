"""Previous billing period: parsing, dating and cumulative chaining."""

import importlib.util
import json
import sys
import unittest
from datetime import UTC, date, datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from brunata_client.errors import PortalFormatError
from brunata_client.models import MediumReadings, MonthlyReading
from brunata_client.parser import parse_previous

from .helpers import FEBRUARY, JANUARY


def chart_with_previous(previous_points, medium="Heizung", copies=1):
    """Synthetic chart in the observed layout: prior period on selected dates."""
    previous = {
        "name": "Vorheriger Abrechnungszeitraum",
        "valueType": "kWh",
        "data": previous_points,
    }
    selected = {
        "name": "Ausgewählter Abrechnungszeitraum",
        "valueType": "kWh",
        "data": [{"x": JANUARY, "y": 12.5, "isHochrechnung": False}],
    }
    return (
        '<script type="text/plain" id="chart-data-chart_0">'
        '{"chart":{"mediumType":'
        + json.dumps(medium)
        + '},"series":'
        + json.dumps([previous] * copies + [selected])
        + "}</script>"
    )


class PreviousPeriodParserTests(unittest.TestCase):
    def test_points_move_to_the_same_month_one_year_earlier(self):
        # The portal sends no estimate flag on the previous period.
        readings = parse_previous(
            chart_with_previous([{"x": JANUARY, "y": 7.5}, {"x": FEBRUARY, "y": 0}]),
            "Heizung",
        )
        self.assertEqual(
            readings,
            (
                MonthlyReading(date(2024, 1, 1), 7.5, "kWh"),
                MonthlyReading(date(2024, 2, 1), 0.0, "kWh"),
            ),
        )

    def test_null_and_explicit_estimates_are_not_readings(self):
        readings = parse_previous(
            chart_with_previous(
                [
                    {"x": JANUARY, "y": None},
                    {"x": FEBRUARY, "y": 3, "isHochrechnung": True},
                ]
            ),
            "Heizung",
        )
        self.assertEqual(readings, ())

    def test_missing_or_ambiguous_series_fail_closed(self):
        broken = (
            chart_with_previous([{"y": 900}]),
            chart_with_previous([{"x": JANUARY, "y": 1}], copies=2),
            chart_with_previous([{"x": JANUARY, "y": 1}], copies=0),
            chart_with_previous([{"x": JANUARY, "y": 1}], medium="Kaltwasser"),
        )
        for source in broken:
            with self.subTest(source=source), self.assertRaises(PortalFormatError):
                parse_previous(source, "Heizung")


class PreviousPeriodStatisticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_previous_year_is_imported_first_and_chains_the_sum(self):
        modules = {
            name: ModuleType(name)
            for name in (
                "homeassistant",
                "homeassistant.components",
                "homeassistant.components.recorder",
                "homeassistant.components.recorder.models",
                "homeassistant.components.recorder.statistics",
            )
        }
        worker = AsyncMock(return_value={})
        modules["homeassistant.components.recorder"].get_instance = Mock(
            return_value=SimpleNamespace(async_add_executor_job=worker)
        )
        modules[
            "homeassistant.components.recorder.models"
        ].StatisticMeanType = SimpleNamespace(NONE=0)
        api = modules["homeassistant.components.recorder.statistics"]
        api.async_add_external_statistics = Mock()
        api.statistics_during_period = Mock()
        source = (
            Path(__file__).resolve().parents[1]
            / "custom_components/brunata_koeln/statistics.py"
        )
        spec = importlib.util.spec_from_file_location(
            "brunata_client.statistics", source
        )
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules):
            spec.loader.exec_module(module)
        clock = Mock()
        clock.now.return_value = datetime(2026, 10, 18)
        clock.side_effect = datetime
        entry = SimpleNamespace(unique_id="synthetic")
        data = {
            "Heizung": MediumReadings(
                "Heizung",
                (MonthlyReading(date(2026, 1, 1), 10, "kWh"),),
                previous=tuple(
                    MonthlyReading(date(2025, month, 1), 1.5, "kWh")
                    for month in range(1, 13)
                ),
            )
        }
        with patch.object(module, "datetime", clock):
            await module.import_history("hass", entry, data)
        calls = api.async_add_external_statistics.call_args_list
        ids = [call.args[1]["statistic_id"] for call in calls]
        self.assertEqual(
            ids,
            [
                "brunata_koeln:synthetic_heating",
                "brunata_koeln:synthetic_heating",
                "brunata_koeln:synthetic_heating_daily_average",
                "brunata_koeln:synthetic_heating_daily_average",
            ],
        )
        prior, current, prior_daily, current_daily = (call.args[2] for call in calls)
        self.assertEqual(prior[0]["start"], datetime(2024, 12, 31, 23, tzinfo=UTC))
        self.assertEqual(prior[-1]["sum"], 18)
        self.assertEqual(current[0]["sum"], 18)
        self.assertEqual(current[-1]["sum"], 28)
        self.assertEqual(prior_daily[-1]["sum"], 18)
        self.assertEqual(current_daily[0]["sum"], 18)
        # Only the oldest imported year asks Recorder for a stored baseline.
        self.assertEqual(worker.await_count, 2)
        for call in worker.await_args_list:
            self.assertEqual(call.args[0].args[2].year, 2024)


if __name__ == "__main__":
    unittest.main()
