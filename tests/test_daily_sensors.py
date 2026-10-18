"""Exercise daily entity values with minimal HA interface doubles."""

import importlib.util
import sys
import unittest
from datetime import date
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from brunata_client.models import MediumReadings, MonthlyReading


class CoordinatorEntity:
    def __class_getitem__(cls, item):
        return cls

    def __init__(self, coordinator):
        self.coordinator = coordinator

    @property
    def available(self):
        return self.coordinator.last_update_success


class DailySensorTests(unittest.TestCase):
    def test_values_labels_missing_comparison_and_source_units(self):
        modules = {
            name: ModuleType(name)
            for name in (
                "homeassistant",
                "homeassistant.components",
                "homeassistant.components.sensor",
                "homeassistant.core",
                "homeassistant.helpers",
                "homeassistant.helpers.entity_platform",
                "homeassistant.helpers.update_coordinator",
                "brunata_client.coordinator",
            )
        }
        modules["homeassistant.components.sensor"].SensorEntity = type(
            "SensorEntity", (), {}
        )
        modules["homeassistant.components.sensor"].SensorDeviceClass = SimpleNamespace(
            ENERGY="energy", WATER="water"
        )
        modules["homeassistant.core"].HomeAssistant = object
        modules["homeassistant.core"].callback = lambda x: x
        modules["homeassistant.helpers.entity_platform"].AddEntitiesCallback = object
        modules[
            "homeassistant.helpers.update_coordinator"
        ].CoordinatorEntity = CoordinatorEntity
        modules["brunata_client.coordinator"].BrunataCoordinator = object
        source = (
            Path(__file__).resolve().parents[1]
            / "custom_components/brunata_koeln/sensor.py"
        )
        spec = importlib.util.spec_from_file_location("brunata_client.sensor", source)
        module = importlib.util.module_from_spec(spec)
        with (
            patch.dict(sys.modules, modules),
            patch.object(
                sys.modules["brunata_client"], "BrunataConfigEntry", object, create=True
            ),
        ):
            spec.loader.exec_module(module)
        own = MonthlyReading(date(2024, 2, 1), 58, "kWh")
        average = MonthlyReading(own.month, 29, "kWh")
        entry = SimpleNamespace(unique_id="synthetic")
        coordinator = SimpleNamespace(
            data={"Heizung": MediumReadings("Heizung", (own,), (average,))},
            entry=entry,
            last_update_success=True,
        )
        sensor = module.BrunataDailyAverageSensor(coordinator, entry, "Heizung", False)
        comparison = module.BrunataDailyAverageSensor(
            coordinator, entry, "Heizung", True
        )
        self.assertEqual(sensor.native_value, 2)
        self.assertEqual(comparison.native_value, 1)
        self.assertEqual(sensor._attr_native_unit_of_measurement, "kWh/d")
        self.assertTrue(sensor.available)
        self.assertTrue(comparison.available)
        self.assertEqual(sensor.extra_state_attributes["source_monthly_value"], 58)
        self.assertNotEqual(
            sensor.extra_state_attributes["statistic_id"],
            comparison.extra_state_attributes["statistic_id"],
        )
        coordinator.data["Heizung"] = MediumReadings("Heizung", (own,), ())
        self.assertFalse(comparison.available)
        self.assertIsNone(comparison.native_value)
        self.assertTrue(sensor.available)
        from datetime import datetime
        from zoneinfo import ZoneInfo

        current = datetime.now(ZoneInfo("Europe/Berlin")).date().replace(day=1)
        forecast = MonthlyReading(current, 310, "kWh")
        coordinator.data["Heizung"] = MediumReadings(
            "Heizung", (own,), (), (forecast,), (forecast,)
        )
        self.assertEqual(sensor.extra_state_attributes["data_basis"], "forecast")
        self.assertEqual(comparison.extra_state_attributes["data_basis"], "forecast")
        self.assertTrue(comparison.available)
        self.assertEqual(sensor.extra_state_attributes["month"], current.isoformat())
        # A first installation may have a current forecast but no actual month.
        coordinator.data["Heizung"] = MediumReadings(
            "Heizung", (), (), (forecast,), (forecast,)
        )
        fresh = module.BrunataDailyAverageSensor(coordinator, entry, "Heizung", False)
        fresh_property = module.BrunataDailyAverageSensor(
            coordinator, entry, "Heizung", True
        )
        self.assertTrue(fresh.available)
        self.assertTrue(fresh_property.available)
        self.assertEqual(fresh.extra_state_attributes["data_basis"], "forecast")
        import asyncio
        from unittest.mock import Mock

        listener = []
        coordinator.async_add_listener = lambda fn: (
            listener.append(fn) or (lambda: None)
        )
        entry.runtime_data = SimpleNamespace(coordinator=coordinator)
        entry.async_on_unload = Mock()
        entities = []
        asyncio.run(module.async_setup_entry(None, entry, entities.extend))
        self.assertEqual(len(entities), 2)
        self.assertTrue(
            all(isinstance(x, module.BrunataDailyAverageSensor) for x in entities)
        )
        coordinator.data["Heizung"] = MediumReadings("Heizung", (own,), (average,))
        listener[0]()
        self.assertEqual(len(entities), 5)
        listener[0]()
        self.assertEqual(len(entities), 5)
        coordinator.last_update_success = False
        self.assertFalse(sensor.available)
