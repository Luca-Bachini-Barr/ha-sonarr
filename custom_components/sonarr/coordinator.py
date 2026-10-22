"""Data update coordinator for the Sonarr integration."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, TypeVar, override

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import SonarrAuthenticationError, SonarrClient, SonarrError
from .const import CONF_UPCOMING_DAYS, CONF_WANTED_MAX_ITEMS, DOMAIN, LOGGER

SonarrDataT = TypeVar("SonarrDataT", bound=dict[str, Any] | list[dict[str, Any]])


@dataclass
class SonarrData:
    """Sonarr data type."""

    upcoming: CalendarDataUpdateCoordinator
    commands: CommandsDataUpdateCoordinator
    diskspace: DiskSpaceDataUpdateCoordinator
    health: HealthDataUpdateCoordinator
    queue: QueueDataUpdateCoordinator
    series: SeriesDataUpdateCoordinator
    status: StatusDataUpdateCoordinator
    wanted: WantedDataUpdateCoordinator
    cutoff: CutoffDataUpdateCoordinator


type SonarrConfigEntry = ConfigEntry[SonarrData]


class SonarrDataUpdateCoordinator(DataUpdateCoordinator[SonarrDataT]):
    """Data update coordinator for the Sonarr integration."""

    config_entry: SonarrConfigEntry
    # How often this endpoint is polled; heavy endpoints poll less often.
    interval = timedelta(seconds=30)

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SonarrConfigEntry,
        api_client: SonarrClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{type(self).__name__}",
            update_interval=self.interval,
        )
        self.api_client = api_client
        self.system_version: str | None = None

    @override
    async def _async_update_data(self) -> SonarrDataT:
        """Get the latest data from Sonarr."""
        try:
            return await self._fetch_data()
        except SonarrAuthenticationError as ex:
            raise ConfigEntryAuthFailed(
                "API Key is no longer valid. Please reauthenticate"
            ) from ex
        except SonarrError as ex:
            raise UpdateFailed(str(ex)) from ex

    async def _fetch_data(self) -> SonarrDataT:
        """Fetch the actual data."""
        raise NotImplementedError


class CalendarDataUpdateCoordinator(SonarrDataUpdateCoordinator[list[dict[str, Any]]]):
    """Calendar update coordinator."""

    interval = timedelta(minutes=5)

    @override
    async def _fetch_data(self) -> list[dict[str, Any]]:
        """Fetch episodes airing in the configured window."""
        start = dt_util.as_utc(dt_util.start_of_local_day())
        end = start + timedelta(days=self.config_entry.options[CONF_UPCOMING_DAYS])
        return await self.api_client.get_calendar(start, end)


class CommandsDataUpdateCoordinator(SonarrDataUpdateCoordinator[list[dict[str, Any]]]):
    """Commands update coordinator for Sonarr."""

    interval = timedelta(minutes=1)

    @override
    async def _fetch_data(self) -> list[dict[str, Any]]:
        """Fetch the data."""
        return await self.api_client.get_commands()


class DiskSpaceDataUpdateCoordinator(SonarrDataUpdateCoordinator[list[dict[str, Any]]]):
    """Disk space update coordinator for Sonarr."""

    interval = timedelta(minutes=5)

    @override
    async def _fetch_data(self) -> list[dict[str, Any]]:
        """Fetch the data."""
        return await self.api_client.get_diskspace()


class HealthDataUpdateCoordinator(SonarrDataUpdateCoordinator[list[dict[str, Any]]]):
    """Health check update coordinator."""

    interval = timedelta(minutes=1)

    @override
    async def _fetch_data(self) -> list[dict[str, Any]]:
        """Fetch the data."""
        return await self.api_client.get_health()


class QueueDataUpdateCoordinator(SonarrDataUpdateCoordinator[dict[str, Any]]):
    """Queue update coordinator."""

    @override
    async def _fetch_data(self) -> dict[str, Any]:
        """Fetch the data."""
        return await self.api_client.get_queue()


class SeriesDataUpdateCoordinator(SonarrDataUpdateCoordinator[list[dict[str, Any]]]):
    """Series update coordinator."""

    interval = timedelta(minutes=15)

    @override
    async def _fetch_data(self) -> list[dict[str, Any]]:
        """Fetch the data."""
        return await self.api_client.get_series()


class StatusDataUpdateCoordinator(SonarrDataUpdateCoordinator[dict[str, Any]]):
    """Status update coordinator for Sonarr."""

    interval = timedelta(hours=1)

    @override
    async def _fetch_data(self) -> dict[str, Any]:
        """Fetch the data."""
        return await self.api_client.get_system_status()


class WantedDataUpdateCoordinator(SonarrDataUpdateCoordinator[dict[str, Any]]):
    """Wanted (missing) update coordinator."""

    interval = timedelta(minutes=5)

    @override
    async def _fetch_data(self) -> dict[str, Any]:
        """Fetch the data."""
        return await self.api_client.get_wanted_missing(
            self.config_entry.options[CONF_WANTED_MAX_ITEMS]
        )


class CutoffDataUpdateCoordinator(SonarrDataUpdateCoordinator[dict[str, Any]]):
    """Wanted (cutoff unmet) update coordinator."""

    interval = timedelta(minutes=5)

    @override
    async def _fetch_data(self) -> dict[str, Any]:
        """Fetch the data."""
        return await self.api_client.get_wanted_cutoff(
            self.config_entry.options[CONF_WANTED_MAX_ITEMS]
        )
