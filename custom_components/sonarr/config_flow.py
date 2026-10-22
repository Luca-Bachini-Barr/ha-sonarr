"""Config flow for Sonarr."""

from collections.abc import Mapping
import logging
from typing import Any, override

import probatio
import yarl

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import SectionConfig, section
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    SonarrAuthenticationError,
    SonarrClient,
    SonarrError,
    SonarrUnsupportedVersionError,
)
from .const import (
    CONF_MORE_OPTIONS,
    CONF_UPCOMING_DAYS,
    CONF_WANTED_MAX_ITEMS,
    DEFAULT_UPCOMING_DAYS,
    DEFAULT_VERIFY_SSL,
    DEFAULT_WANTED_MAX_ITEMS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect to a Sonarr v5 server."""
    sonarr = SonarrClient(
        async_get_clientsession(hass, verify_ssl=data[CONF_VERIFY_SSL]),
        data[CONF_URL],
        data[CONF_API_KEY],
    )
    await sonarr.get_system_status()


class SonarrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sonarr."""

    VERSION = 2

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> SonarrOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SonarrOptionsFlowHandler()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                description_placeholders={
                    "url": self._get_reauth_entry().data[CONF_URL]
                },
                errors={},
            )

        return await self.async_step_user()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            more_options = user_input.pop(CONF_MORE_OPTIONS, {})
            user_input[CONF_VERIFY_SSL] = more_options.get(
                CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL
            )
            if CONF_URL in user_input:
                user_input[CONF_URL] = user_input[CONF_URL].rstrip("/")

            if self.source == SOURCE_REAUTH:
                user_input = {**self._get_reauth_entry().data, **user_input}

            try:
                await _validate_input(self.hass, user_input)
            except SonarrAuthenticationError:
                errors = {"base": "invalid_auth"}
            except SonarrUnsupportedVersionError:
                errors = {"base": "unsupported_version"}
            except SonarrError:
                errors = {"base": "cannot_connect"}
            except Exception:
                _LOGGER.exception("Unexpected exception")
                return self.async_abort(reason="unknown")
            else:
                if self.source == SOURCE_REAUTH:
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(), data=user_input
                    )

                parsed = yarl.URL(user_input[CONF_URL])

                return self.async_create_entry(
                    title=parsed.host or "Sonarr", data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self._get_user_data_schema(),
            errors=errors,
        )

    def _get_user_data_schema(self) -> probatio.Schema:
        """Get the data schema to display user form."""
        if self.source == SOURCE_REAUTH:
            return probatio.Schema({probatio.Required(CONF_API_KEY): str})

        return probatio.Schema(
            {
                probatio.Required(CONF_URL): str,
                probatio.Required(CONF_API_KEY): str,
                probatio.Required(CONF_MORE_OPTIONS): section(
                    probatio.Schema(
                        {
                            probatio.Optional(
                                CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL
                            ): bool,
                        }
                    ),
                    SectionConfig(collapsed=True),
                ),
            }
        )


class SonarrOptionsFlowHandler(OptionsFlowWithReload):
    """Handle Sonarr client options."""

    async def async_step_init(
        self, user_input: dict[str, int] | None = None
    ) -> ConfigFlowResult:
        """Manage Sonarr options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            probatio.Optional(
                CONF_UPCOMING_DAYS,
                default=self.config_entry.options.get(
                    CONF_UPCOMING_DAYS, DEFAULT_UPCOMING_DAYS
                ),
            ): int,
            probatio.Optional(
                CONF_WANTED_MAX_ITEMS,
                default=self.config_entry.options.get(
                    CONF_WANTED_MAX_ITEMS, DEFAULT_WANTED_MAX_ITEMS
                ),
            ): int,
        }

        return self.async_show_form(
            step_id="init", data_schema=probatio.Schema(options)
        )
