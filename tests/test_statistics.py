"""Verify recorder API orchestration with isolated interface doubles, not HA."""

import importlib.util
import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from brunata_client.models import MediumReadings, MonthlyReading


class StatisticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_import_uses_stable_id_and_previous_year_baseline(self):
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
        recorder = modules["homeassistant.components.recorder"]
        worker = AsyncMock(
            return_value={"brunata_koeln:synthetic_heating": [{"sum": 120}]}
        )
        recorder.get_instance = Mock(
            return_value=SimpleNamespace(async_add_executor_job=worker)
        )
        models = modules["homeassistant.components.recorder.models"]
        models.StatisticMeanType = SimpleNamespace(NONE=0)
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
        # Calls creating datetime boundaries still use real datetime.
        clock.side_effect = datetime
        entry = SimpleNamespace(unique_id="synthetic")
        data = {
            "Heizung": MediumReadings(
                "Heizung", (MonthlyReading(date(2026, 1, 1), 10, "kWh"),)
            )
        }
        with patch.object(module, "datetime", clock):
            await module.import_history("hass", entry, data)
            await module.import_history("hass", entry, data)
        first, daily_first, second, daily_second = (
            api.async_add_external_statistics.call_args_list
        )
        self.assertEqual(daily_first, daily_second)
        self.assertTrue(daily_first.args[1]["statistic_id"].endswith("_daily_average"))
        self.assertEqual(first, second)
        metadata, rows = first.args[1:]
        self.assertEqual(metadata["statistic_id"], "brunata_koeln:synthetic_heating")
        self.assertEqual(metadata["unit_class"], "energy")
        self.assertEqual(metadata["mean_type"], 0)
        self.assertEqual(rows[0]["sum"], 120)
        self.assertEqual(rows[-1]["sum"], 130)
        data["Heizung"] = MediumReadings(
            "Heizung",
            data["Heizung"].readings,
            (MonthlyReading(date(2026, 1, 1), 5, "kWh"),),
        )
        api.async_add_external_statistics.reset_mock()
        with patch.object(module, "datetime", clock):
            await module.import_history("hass", entry, data)
        imports = api.async_add_external_statistics.call_args_list
        self.assertEqual(len(imports), 4)
        ids = [call.args[1]["statistic_id"] for call in imports]
        self.assertEqual(len(set(ids)), 4)
        self.assertTrue(ids[2].endswith("_property_average"))
        self.assertTrue(ids[3].endswith("_property_daily_average"))
        self.assertEqual(imports[2].args[2][-1]["sum"], 5)
        self.assertEqual(imports[3].args[2][-1]["sum"], 5)
        data["Heizung"] = MediumReadings(
            "Heizung",
            data["Heizung"].readings,
            forecasts=(MonthlyReading(date(2026, 2, 1), 56, "kWh"),),
        )
        api.async_add_external_statistics.reset_mock()
        with patch.object(module, "datetime", clock):
            await module.import_history("hass", entry, data)
        actual_import, daily_import = api.async_add_external_statistics.call_args_list
        self.assertEqual(actual_import.args[2][-1]["sum"], 130)
        self.assertEqual(daily_import.args[2][-1]["sum"], 66)
        query = worker.call_args.args[0]
        self.assertEqual(
            query.args[1].year, 2024
        )  # UTC: Berlin January 1 is previous day.
        self.assertEqual(query.args[2].year, 2025)
