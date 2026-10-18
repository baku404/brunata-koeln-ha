"""BRUNATA-METRONA Cologne monthly consumption integration."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .api import BrunataClient
from .coordinator import BrunataCoordinator

PLATFORMS = [Platform.SENSOR]


@dataclass
class BrunataRuntime:
    """Account-isolated integration state."""

    client: BrunataClient
    coordinator: BrunataCoordinator


type BrunataConfigEntry = ConfigEntry[BrunataRuntime]


async def async_setup_entry(hass: HomeAssistant, entry: BrunataConfigEntry) -> bool:
    """Fetch once before adding any entities."""
    client = BrunataClient(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    coordinator = BrunataCoordinator(hass, entry, client)
    try:
        await coordinator.async_config_entry_first_refresh()
    except BaseException:
        await client.async_close()
        raise
    entry.runtime_data = BrunataRuntime(client, coordinator)
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await client.async_close()
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BrunataConfigEntry) -> bool:
    """Unload entities and close the account's private HTTP session."""
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.client.async_close()
        return True
    return False
