"""Support for Sonarr calendar items."""

from datetime import datetime, timedelta
from typing import Any, override

from homeassistant.components.calendar import (
    CalendarEntity,
    CalendarEntityDescription,
    CalendarEvent,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import SonarrError
from .coordinator import CalendarDataUpdateCoordinator, SonarrConfigEntry
from .entity import SonarrEntity
from .helpers import episode_identifier, series_title

CALENDAR_TYPE = CalendarEntityDescription(
    key="calendar",
    name=None,
)

# Used when neither the episode nor the series has a runtime yet.
DEFAULT_RUNTIME = 30


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SonarrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Sonarr calendar entity."""
    coordinator = entry.runtime_data.upcoming
    async_add_entities([SonarrCalendarEntity(coordinator, CALENDAR_TYPE)])


def _get_calendar_event(episode: dict[str, Any]) -> CalendarEvent | None:
    """Return a CalendarEvent from a Sonarr calendar item."""
    if not (aired := episode.get("airDateUtc")) or not (
        start := dt_util.parse_datetime(aired)
    ):
        return None
    runtime = (
        episode.get("runtime")
        or (episode.get("series") or {}).get("runtime")
        or DEFAULT_RUNTIME
    )
    summary = f"{series_title(episode)} - {episode_identifier(episode)}"
    if episode.get("title"):
        summary = f"{summary} - {episode['title']}"
    start = dt_util.as_utc(start)
    return CalendarEvent(
        summary=summary,
        start=start,
        end=start + timedelta(minutes=runtime),
        description=episode.get("overview") or None,
    )


def _get_calendar_events(episodes: list[dict[str, Any]]) -> list[CalendarEvent]:
    return [event for e in episodes if (event := _get_calendar_event(e)) is not None]


class SonarrCalendarEntity(SonarrEntity[list[dict[str, Any]]], CalendarEntity):
    """A Sonarr calendar entity."""

    coordinator: CalendarDataUpdateCoordinator

    @property
    @override
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        now = dt_util.now()
        events = sorted(
            _get_calendar_events(self.coordinator.data), key=lambda event: event.start
        )
        return next((event for event in events if event.end > now), None)

    @override
    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        try:
            episodes = await self.coordinator.api_client.get_calendar(
                dt_util.as_utc(start_date), dt_util.as_utc(end_date)
            )
        except SonarrError as err:
            raise HomeAssistantError(f"Unable to fetch Sonarr calendar: {err}") from err
        return _get_calendar_events(episodes)
