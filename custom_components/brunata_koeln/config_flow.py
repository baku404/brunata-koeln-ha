"""Validate Cologne credentials without retaining portal responses."""

import hashlib
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .api import BrunataClient
from .const import DOMAIN
from .errors import (
    AuthenticationError,
    CaptchaRequired,
    ConnectionError,
    NoSupportedData,
    PortalFormatError,
)


class BrunataKoelnConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure one account after validating its consumption response."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create a validated account entry."""
        errors = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            identity = hashlib.sha256(username.casefold().encode()).hexdigest()
            await self.async_set_unique_id(identity)
            self._abort_if_unique_id_configured()
            errors = await self._validate(username, user_input[CONF_PASSWORD])
            if not errors:
                return self.async_create_entry(
                    title="BRUNATA-METRONA Cologne",
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
            ),
            errors=errors,
        )

    async def _validate(self, username: str, password: str) -> dict[str, str]:
        if not username or not password:
            return {"base": "invalid_auth"}
        client = BrunataClient(username, password)
        try:
            await client.async_fetch()
        except CaptchaRequired:
            return {"base": "captcha_required"}
        except AuthenticationError:
            return {"base": "invalid_auth"}
        except ConnectionError:
            return {"base": "cannot_connect"}
        except NoSupportedData:
            return {"base": "no_supported_data"}
        except PortalFormatError:
            return {"base": "portal_changed"}
        finally:
            await client.async_close()
        return {}

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Keep the original account identity when reauthenticating."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update only the existing account's password."""
        entry = self._get_reauth_entry()
        errors = {}
        if user_input is not None:
            errors = await self._validate(
                entry.data[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )
