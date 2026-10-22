"""The Sonarr component (v5 API fork)."""

import asyncio
from dataclasses import fields

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_URL,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import SonarrClient
from .const import (
    CONF_BASE_PATH,
    CONF_UPCOMING_DAYS,
    CONF_WANTED_MAX_ITEMS,
    DEFAULT_UPCOMING_DAYS,
    DEFAULT_WANTED_MAX_ITEMS,
    DOMAIN,
    LOGGER,
)
from .coordinator import (
    CalendarDataUpdateCoordinator,
    CommandsDataUpdateCoordinator,
    CutoffDataUpdateCoordinator,
    DiskSpaceDataUpdateCoordinator,
    HealthDataUpdateCoordinator,
    QueueDataUpdateCoordinator,
    SeriesDataUpdateCoordinator,
    SonarrConfigEntry,
    SonarrData,
    StatusDataUpdateCoordinator,
    WantedDataUpdateCoordinator,
)
from .services import async_setup_services

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.CALENDAR, Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Sonarr integration."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SonarrConfigEntry) -> bool:
    """Set up Sonarr from a config entry."""
    if not entry.options:
        options = {
            CONF_UPCOMING_DAYS: entry.data.get(
                CONF_UPCOMING_DAYS, DEFAULT_UPCOMING_DAYS
            ),
            CONF_WANTED_MAX_ITEMS: entry.data.get(
                CONF_WANTED_MAX_ITEMS, DEFAULT_WANTED_MAX_ITEMS
            ),
        }
        hass.config_entries.async_update_entry(entry, options=options)

    sonarr = SonarrClient(
        async_get_clientsession(hass, verify_ssl=entry.data[CONF_VERIFY_SSL]),
        entry.data[CONF_URL],
        entry.data[CONF_API_KEY],
    )
    data = SonarrData(
        upcoming=CalendarDataUpdateCoordinator(hass, entry, sonarr),
        commands=CommandsDataUpdateCoordinator(hass, entry, sonarr),
        diskspace=DiskSpaceDataUpdateCoordinator(hass, entry, sonarr),
        health=HealthDataUpdateCoordinator(hass, entry, sonarr),
        queue=QueueDataUpdateCoordinator(hass, entry, sonarr),
        series=SeriesDataUpdateCoordinator(hass, entry, sonarr),
        status=StatusDataUpdateCoordinator(hass, entry, sonarr),
        wanted=WantedDataUpdateCoordinator(hass, entry, sonarr),
        cutoff=CutoffDataUpdateCoordinator(hass, entry, sonarr),
    )
    coordinators = [getattr(data, field.name) for field in fields(data)]
    await asyncio.gather(
        *(c.async_config_entry_first_refresh() for c in coordinators)
    )
    version = data.status.data.get("version")
    for coordinator in coordinators:
        coordinator.system_version = version
    entry.runtime_data = data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    LOGGER.debug("Migrating from version %s", entry.version)

    if entry.version == 1:
        new_proto = "https" if entry.data[CONF_SSL] else "http"
        new_host_port = f"{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}"

        new_path = ""

        if entry.data[CONF_BASE_PATH].rstrip("/") not in ("", "/", "/api"):
            new_path = entry.data[CONF_BASE_PATH].rstrip("/")

        data = {
            **entry.data,
            CONF_URL: f"{new_proto}://{new_host_port}{new_path}",
        }
        hass.config_entries.async_update_entry(entry, data=data, version=2)

    LOGGER.debug("Migration to version %s successful", entry.version)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SonarrConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
