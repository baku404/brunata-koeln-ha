"""Expose reported monthly consumption without claiming a cumulative meter."""

from calendar import monthrange

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BrunataConfigEntry
from .const import DOMAIN
from .coordinator import BrunataCoordinator
from .models import daily_sources
from .parser import MEDIA

LABELS = {"Heizung": "Heating", "Kaltwasser": "Cold water", "Warmwasser": "Hot water"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BrunataConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Discover media dynamically while retaining stable entity identities."""
    coordinator = entry.runtime_data.coordinator
    added: set[str] = set()

    @callback
    def discover():
        entities = []
        for medium, data in (coordinator.data or {}).items():
            if medium not in added and data.latest is not None:
                added.add(medium)
                entities.append(BrunataMonthlySensor(coordinator, entry, medium))
            for property_basis in (False, True):
                key = f"{medium}_daily_{property_basis}"
                if key not in added and daily_sources(data, property_basis):
                    added.add(key)
                    entities.append(
                        BrunataDailyAverageSensor(
                            coordinator, entry, medium, property_basis
                        )
                    )
            for kind in ("property_average", "property_deviation"):
                key = f"{medium}_{kind}"
                if (
                    key not in added
                    and data.latest is not None
                    and data.property_average
                ):
                    added.add(key)
                    entities.append(
                        BrunataComparisonSensor(coordinator, entry, medium, kind)
                    )
        async_add_entities(entities)

    discover()
    entry.async_on_unload(coordinator.async_add_listener(discover))


class BrunataMonthlySensor(CoordinatorEntity[BrunataCoordinator], SensorEntity):
    """Latest actual past-month consumption; no long-term statistics state class."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: BrunataCoordinator, entry: BrunataConfigEntry, medium: str
    ):
        super().__init__(coordinator)
        self.medium = medium
        data = coordinator.data[medium]
        latest = data.latest
        if latest is None:
            available = daily_sources(data) or daily_sources(data, True)
            if not available:
                raise ValueError("No monthly source is available for the sensor")
            latest = available[-1]
        self._unit = latest.unit
        self._attr_unique_id = f"{entry.unique_id}_{MEDIA[medium]}_monthly"
        self._attr_name = f"{LABELS[medium]} latest reported month"
        self._attr_icon = "mdi:radiator" if medium == "Heizung" else "mdi:water"
        self._attr_native_unit_of_measurement = self._unit
        self._attr_device_class = (
            SensorDeviceClass.ENERGY if self._unit == "kWh" else SensorDeviceClass.WATER
        )
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.unique_id)},
            "name": "BRUNATA-METRONA Cologne",
            "manufacturer": "BRUNATA-METRONA",
        }

    @property
    def _latest(self):
        data = (self.coordinator.data or {}).get(self.medium)
        return data.latest if data else None

    @property
    def available(self) -> bool:
        """Reject missing readings and unit changes without corrupting history."""
        latest = self._latest
        return super().available and latest is not None and latest.unit == self._unit

    @property
    def native_value(self) -> float | None:
        latest = self._latest
        return latest.value if latest and latest.unit == self._unit else None

    @property
    def extra_state_attributes(self):
        latest = self._latest
        return {
            "month": latest.month.isoformat() if latest else None,
            "source_medium": self.medium,
            "measurement_type": "monthly_consumption",
            "estimated": False,
        }


class BrunataComparisonSensor(BrunataMonthlySensor):
    """Property average and own deviation for the latest own reported month."""

    _attr_suggested_display_precision = 3

    def __init__(self, coordinator, entry, medium, kind):
        super().__init__(coordinator, entry, medium)
        self.kind = kind
        self._attr_icon = (
            "mdi:home-group" if kind == "property_average" else "mdi:delta"
        )
        self._attr_unique_id = f"{entry.unique_id}_{MEDIA[medium]}_{kind}"
        self._attr_name = f"{LABELS[medium]} " + (
            "property average"
            if kind == "property_average"
            else "deviation from property average"
        )
        self._attr_device_class = None
        self._attr_native_unit_of_measurement = (
            self._unit if kind == "property_average" else "%"
        )

    @property
    def _comparison(self):
        latest = self._latest
        data = (self.coordinator.data or {}).get(self.medium)
        if latest is None or data is None:
            return None
        return next(
            (
                x
                for x in data.property_average
                if x.month == latest.month and x.unit == self._unit
            ),
            None,
        )

    @property
    def available(self):
        average = self._comparison
        return (
            super().available
            and average is not None
            and (self.kind == "property_average" or average.value > 0)
        )

    @property
    def native_value(self):
        average = self._comparison
        if average is None:
            return None
        if self.kind == "property_average":
            return average.value
        return (
            (self._latest.value / average.value - 1) * 100
            if average.value > 0
            else None
        )

    @property
    def extra_state_attributes(self):
        return {
            **super().extra_state_attributes,
            "measurement_type": self.kind,
            "comparison_basis": "per_tenancy",
            "normalization": "unadjusted",
        }


class BrunataDailyAverageSensor(BrunataMonthlySensor):
    """Latest reported month's average daily distribution, not today's usage."""

    _attr_suggested_display_precision = 3

    def __init__(self, coordinator, entry, medium, property_basis):
        super().__init__(coordinator, entry, medium)
        self.property_basis = property_basis
        self._attr_suggested_display_precision = 3
        self._attr_icon = (
            "mdi:home-group"
            if property_basis
            else ("mdi:radiator" if medium == "Heizung" else "mdi:water")
        )
        suffix = "property_daily_average" if property_basis else "daily_average"
        self._attr_unique_id = f"{entry.unique_id}_{MEDIA[medium]}_{suffix}"
        basis = "property " if property_basis else ""
        self._attr_name = f"{LABELS[medium]} {basis}average daily distribution"
        self._attr_device_class = None
        self._attr_native_unit_of_measurement = f"{self._unit}/d"

    @property
    def _latest(self):
        data = (self.coordinator.data or {}).get(self.medium)
        if data is None:
            return None
        rows = daily_sources(data, self.property_basis)
        return rows[-1] if rows else None

    @property
    def native_value(self):
        latest = self._latest
        if latest is None or latest.unit != self._unit:
            return None
        return latest.value / monthrange(latest.month.year, latest.month.month)[1]

    @property
    def _data_basis(self):
        latest = self._latest
        data = (self.coordinator.data or {}).get(self.medium)
        actual = (
            (data.property_average if self.property_basis else data.readings)
            if data
            else ()
        )
        return (
            "actual"
            if latest and any(x.month == latest.month for x in actual)
            else "forecast"
        )

    @property
    def extra_state_attributes(self):
        latest = self._latest
        suffix = "property_daily_average" if self.property_basis else "daily_average"
        return {
            "month": latest.month.isoformat() if latest else None,
            "source_medium": self.medium,
            "measurement_type": "average_daily_distribution",
            "distribution_method": "monthly_total_divided_by_calendar_days",
            "source_monthly_value": latest.value if latest else None,
            "source_unit": self._unit,
            "data_basis": self._data_basis,
            "comparison_basis": "per_tenancy"
            if self.property_basis
            else "own_consumption",
            "statistic_id": (
                f"{DOMAIN}:{self.coordinator.entry.unique_id}_"
                f"{MEDIA[self.medium]}_{suffix}"
            ),
        }
