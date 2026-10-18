"""Refresh consumption once for all sensors."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BrunataClient
from .const import DOMAIN, UPDATE_INTERVAL
from .errors import AuthenticationError, BrunataError
from .models import MediumReadings
from .statistics import import_history


class BrunataCoordinator(DataUpdateCoordinator[dict[str, MediumReadings]]):
    """Share one daily fetch across the account's entities."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: BrunataClient):
        import logging

        super().__init__(
            hass,
            logging.getLogger(__name__),
            name=DOMAIN,
            config_entry=entry,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self.entry = entry

    async def _async_update_data(self) -> dict[str, MediumReadings]:
        try:
            data = await self.client.async_fetch(include_comparison=True)
            await import_history(self.hass, self.entry, data)
            return data
        except AuthenticationError:
            raise ConfigEntryAuthFailed("Portal authentication required") from None
        except ValueError:
            raise UpdateFailed("Invalid monthly statistics data") from None
        except BrunataError as error:
            raise UpdateFailed(str(error)) from None
