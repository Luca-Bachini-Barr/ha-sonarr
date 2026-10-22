"""Support for Sonarr buttons (commands)."""

from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import SonarrError
from .const import (
    COMMAND_CUTOFF_SEARCH,
    COMMAND_MISSING_SEARCH,
    COMMAND_REFRESH_SERIES,
    COMMAND_RSS_SYNC,
)
from .coordinator import CommandsDataUpdateCoordinator, SonarrConfigEntry
from .entity import SonarrEntity


@dataclass(frozen=True, kw_only=True)
class SonarrButtonEntityDescription(ButtonEntityDescription):
    """Describe a button that queues a Sonarr command."""

    command: str
    body: dict[str, Any]


BUTTON_TYPES: tuple[SonarrButtonEntityDescription, ...] = (
    SonarrButtonEntityDescription(
        key="rss_sync", translation_key="rss_sync", command=COMMAND_RSS_SYNC, body={}
    ),
    SonarrButtonEntityDescription(
        key="refresh_series",
        translation_key="refresh_series",
        command=COMMAND_REFRESH_SERIES,
        body={},
    ),
    SonarrButtonEntityDescription(
        key="search_missing",
        translation_key="search_missing",
        command=COMMAND_MISSING_SEARCH,
        body={"monitored": True},
    ),
    SonarrButtonEntityDescription(
        key="search_cutoff_unmet",
        translation_key="search_cutoff_unmet",
        command=COMMAND_CUTOFF_SEARCH,
        body={"monitored": True},
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SonarrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sonarr buttons."""
    async_add_entities(
        SonarrButton(entry.runtime_data.commands, description)
        for description in BUTTON_TYPES
    )


class SonarrButton(SonarrEntity[list[dict[str, Any]]], ButtonEntity):
    """Queue a Sonarr command when pressed."""

    coordinator: CommandsDataUpdateCoordinator
    entity_description: SonarrButtonEntityDescription

    @override
    async def async_press(self) -> None:
        """Queue the command and refresh the command list."""
        try:
            await self.coordinator.api_client.run_command(
                self.entity_description.command, **self.entity_description.body
            )
        except SonarrError as err:
            raise HomeAssistantError(
                f"Sonarr {self.entity_description.command} failed: {err}"
            ) from err
        await self.coordinator.async_request_refresh()
