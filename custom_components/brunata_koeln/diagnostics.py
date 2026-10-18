"""Allowlisted diagnostics without account identifiers or response bodies."""

from homeassistant.core import HomeAssistant

from . import BrunataConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BrunataConfigEntry
):
    """Report only safe operational status."""
    coordinator = entry.runtime_data.coordinator
    return {
        "last_update_success": coordinator.last_update_success,
        "update_interval_seconds": coordinator.update_interval.total_seconds(),
        "media": [
            {
                "medium": medium,
                "unit": data.latest.unit if data.latest else None,
                "reported_months": len(data.readings),
            }
            for medium, data in (coordinator.data or {}).items()
        ],
    }
