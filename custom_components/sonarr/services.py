"""Define services for the Sonarr integration."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

import probatio

from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, selector, service
from homeassistant.util import dt as dt_util

from .api import SonarrAuthenticationError, SonarrConnectionError, SonarrError
from .const import (
    ATTR_DISKS,
    ATTR_ENTRY_ID,
    ATTR_EPISODES,
    ATTR_SHOWS,
    COMMAND_CUTOFF_SEARCH,
    COMMAND_EPISODE_SEARCH,
    COMMAND_MISSING_SEARCH,
    COMMAND_REFRESH_SERIES,
    COMMAND_RSS_SYNC,
    COMMAND_SERIES_SEARCH,
    DEFAULT_UPCOMING_DAYS,
    DOMAIN,
    SERVICE_GET_CUTOFF_UNMET,
    SERVICE_GET_DISKSPACE,
    SERVICE_GET_EPISODES,
    SERVICE_GET_QUEUE,
    SERVICE_GET_SERIES,
    SERVICE_GET_UPCOMING,
    SERVICE_GET_WANTED,
    SERVICE_GRAB_QUEUE_ITEM,
    SERVICE_REFRESH_SERIES,
    SERVICE_REMOVE_QUEUE_ITEM,
    SERVICE_RSS_SYNC,
    SERVICE_SEARCH_CUTOFF_UNMET,
    SERVICE_SEARCH_EPISODES,
    SERVICE_SEARCH_MISSING,
    SERVICE_SEARCH_SERIES,
)
from .coordinator import SonarrConfigEntry
from .helpers import (
    format_diskspace,
    format_episode_list,
    format_episodes,
    format_queue,
    format_series,
)

# Service parameter constants
CONF_BLOCKLIST_METHOD = "blocklist_method"
CONF_DAYS = "days"
CONF_EPISODE_IDS = "episode_ids"
CONF_MAX_ITEMS = "max_items"
CONF_QUEUE_ID = "queue_id"
CONF_REMOVAL_METHOD = "removal_method"
CONF_SERIES_ID = "series_id"
CONF_SEASON_NUMBER = "season_number"
CONF_SPACE_UNIT = "space_unit"

# Valid space units
SPACE_UNITS = ["bytes", "kb", "kib", "mb", "mib", "gb", "gib", "tb", "tib", "pb", "pib"]
DEFAULT_SPACE_UNIT = "bytes"

REMOVAL_METHODS = ["removeFromClient", "changeCategory", "ignore"]
BLOCKLIST_METHODS = ["doNotBlocklist", "blocklistAndSearch", "blocklistOnly"]

# Default values - 0 means no limit
DEFAULT_MAX_ITEMS = 0

SERVICE_BASE_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_ENTRY_ID): selector.ConfigEntrySelector(
            {"integration": DOMAIN}
        ),
    }
)

SERIES_ID = probatio.All(probatio.Coerce(int), probatio.Range(min=1))
MAX_ITEMS = probatio.All(probatio.Coerce(int), probatio.Range(min=0, max=500))

SERVICE_GET_EPISODES_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {
        probatio.Required(CONF_SERIES_ID): SERIES_ID,
        probatio.Optional(CONF_SEASON_NUMBER): probatio.All(
            probatio.Coerce(int), probatio.Range(min=0)
        ),
    }
)

SERVICE_MAX_ITEMS_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {probatio.Optional(CONF_MAX_ITEMS, default=DEFAULT_MAX_ITEMS): MAX_ITEMS}
)

SERVICE_GET_DISKSPACE_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {
        probatio.Optional(CONF_SPACE_UNIT, default=DEFAULT_SPACE_UNIT): probatio.In(
            SPACE_UNITS
        ),
    }
)

SERVICE_GET_UPCOMING_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {
        probatio.Optional(CONF_DAYS, default=DEFAULT_UPCOMING_DAYS): probatio.All(
            probatio.Coerce(int), probatio.Range(min=1, max=30)
        ),
    }
)

SERVICE_REFRESH_SERIES_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {probatio.Optional(CONF_SERIES_ID): SERIES_ID}
)

SERVICE_SEARCH_SERIES_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {probatio.Required(CONF_SERIES_ID): SERIES_ID}
)

SERVICE_SEARCH_EPISODES_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {
        probatio.Required(CONF_EPISODE_IDS): probatio.All(
            cv.ensure_list, [probatio.Coerce(int)]
        ),
    }
)

SERVICE_QUEUE_ITEM_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {probatio.Required(CONF_QUEUE_ID): SERIES_ID}
)

SERVICE_REMOVE_QUEUE_ITEM_SCHEMA = SERVICE_QUEUE_ITEM_SCHEMA.extend(
    {
        probatio.Optional(
            CONF_REMOVAL_METHOD, default="removeFromClient"
        ): probatio.In(REMOVAL_METHODS),
        probatio.Optional(
            CONF_BLOCKLIST_METHOD, default="doNotBlocklist"
        ): probatio.In(BLOCKLIST_METHODS),
    }
)


async def _handle_api_errors[_T](func: Callable[[], Awaitable[_T]]) -> _T:
    """Handle API errors and raise HomeAssistantError with user-friendly messages."""
    try:
        return await func()
    except SonarrAuthenticationError as ex:
        raise HomeAssistantError("Authentication failed for Sonarr") from ex
    except SonarrConnectionError as ex:
        raise HomeAssistantError("Failed to connect to Sonarr") from ex
    except SonarrError as ex:
        raise HomeAssistantError(f"Sonarr API error: {ex}") from ex


def _get_entry(call: ServiceCall) -> SonarrConfigEntry:
    return service.async_get_config_entry(call.hass, DOMAIN, call.data[ATTR_ENTRY_ID])


def _page_size(call: ServiceCall) -> int:
    # 0 means no limit - use a large page size to get all items
    return call.data[CONF_MAX_ITEMS] or 10000


async def _async_get_series(call: ServiceCall) -> dict[str, Any]:
    """Get all Sonarr series."""
    entry = _get_entry(call)
    series_list = await _handle_api_errors(entry.runtime_data.status.api_client.get_series)
    return {ATTR_SHOWS: format_series(series_list, entry.data[CONF_URL])}


async def _async_get_episodes(call: ServiceCall) -> dict[str, Any]:
    """Get episodes for a specific series."""
    entry = _get_entry(call)
    api_client = entry.runtime_data.status.api_client
    season_number: int | None = call.data.get(CONF_SEASON_NUMBER)
    episodes = await _handle_api_errors(
        lambda: api_client.get_episodes(call.data[CONF_SERIES_ID], season_number)
    )
    return {ATTR_EPISODES: format_episodes(episodes, season_number)}


async def _async_get_queue(call: ServiceCall) -> dict[str, Any]:
    """Get Sonarr queue."""
    entry = _get_entry(call)
    api_client = entry.runtime_data.status.api_client
    queue = await _handle_api_errors(lambda: api_client.get_queue(_page_size(call)))
    return {ATTR_SHOWS: format_queue(queue, entry.data[CONF_URL])}


async def _async_get_diskspace(call: ServiceCall) -> dict[str, Any]:
    """Get Sonarr diskspace information."""
    entry = _get_entry(call)
    disks = await _handle_api_errors(entry.runtime_data.status.api_client.get_diskspace)
    return {ATTR_DISKS: format_diskspace(disks, call.data[CONF_SPACE_UNIT])}


async def _async_get_upcoming(call: ServiceCall) -> dict[str, Any]:
    """Get Sonarr upcoming episodes."""
    entry = _get_entry(call)
    api_client = entry.runtime_data.status.api_client
    start = dt_util.as_utc(dt_util.start_of_local_day())
    end = start + timedelta(days=call.data[CONF_DAYS])
    calendar = await _handle_api_errors(lambda: api_client.get_calendar(start, end))
    return {ATTR_EPISODES: format_episode_list(calendar, entry.data[CONF_URL])}


async def _async_get_wanted(call: ServiceCall) -> dict[str, Any]:
    """Get Sonarr wanted/missing episodes."""
    entry = _get_entry(call)
    api_client = entry.runtime_data.status.api_client
    wanted = await _handle_api_errors(
        lambda: api_client.get_wanted_missing(_page_size(call))
    )
    return {ATTR_EPISODES: format_episode_list(wanted["records"], entry.data[CONF_URL])}


async def _async_get_cutoff_unmet(call: ServiceCall) -> dict[str, Any]:
    """Get Sonarr episodes below their quality cutoff."""
    entry = _get_entry(call)
    api_client = entry.runtime_data.status.api_client
    cutoff = await _handle_api_errors(
        lambda: api_client.get_wanted_cutoff(_page_size(call))
    )
    return {ATTR_EPISODES: format_episode_list(cutoff["records"], entry.data[CONF_URL])}


def _command_handler(
    command: str, body_fn: Callable[[ServiceCall], dict[str, Any]]
) -> Callable[[ServiceCall], Awaitable[dict[str, Any]]]:
    """Build a service handler that queues a Sonarr command."""

    async def _handler(call: ServiceCall) -> dict[str, Any]:
        entry = _get_entry(call)
        result = await _handle_api_errors(
            lambda: entry.runtime_data.commands.api_client.run_command(
                command, **body_fn(call)
            )
        )
        await entry.runtime_data.commands.async_request_refresh()
        return {"command_id": result.get("id"), "status": result.get("status")}

    return _handler


def _series_body(call: ServiceCall) -> dict[str, Any]:
    if CONF_SERIES_ID in call.data:
        return {"seriesId": call.data[CONF_SERIES_ID]}
    return {}


async def _async_remove_queue_item(call: ServiceCall) -> None:
    """Remove a download from the Sonarr queue."""
    entry = _get_entry(call)
    await _handle_api_errors(
        lambda: entry.runtime_data.queue.api_client.remove_queue_item(
            call.data[CONF_QUEUE_ID],
            call.data[CONF_REMOVAL_METHOD],
            call.data[CONF_BLOCKLIST_METHOD],
        )
    )
    await entry.runtime_data.queue.async_request_refresh()


async def _async_grab_queue_item(call: ServiceCall) -> None:
    """Force-grab a delayed release in the Sonarr queue."""
    entry = _get_entry(call)
    await _handle_api_errors(
        lambda: entry.runtime_data.queue.api_client.grab_queue_item(
            call.data[CONF_QUEUE_ID]
        )
    )
    await entry.runtime_data.queue.async_request_refresh()


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services for the Sonarr integration."""
    read_services: dict[str, tuple[Callable, probatio.Schema]] = {
        SERVICE_GET_SERIES: (_async_get_series, SERVICE_BASE_SCHEMA),
        SERVICE_GET_EPISODES: (_async_get_episodes, SERVICE_GET_EPISODES_SCHEMA),
        SERVICE_GET_QUEUE: (_async_get_queue, SERVICE_MAX_ITEMS_SCHEMA),
        SERVICE_GET_DISKSPACE: (_async_get_diskspace, SERVICE_GET_DISKSPACE_SCHEMA),
        SERVICE_GET_UPCOMING: (_async_get_upcoming, SERVICE_GET_UPCOMING_SCHEMA),
        SERVICE_GET_WANTED: (_async_get_wanted, SERVICE_MAX_ITEMS_SCHEMA),
        SERVICE_GET_CUTOFF_UNMET: (_async_get_cutoff_unmet, SERVICE_MAX_ITEMS_SCHEMA),
    }
    for name, (handler, schema) in read_services.items():
        hass.services.async_register(
            DOMAIN, name, handler, schema=schema, supports_response=SupportsResponse.ONLY
        )

    command_services: dict[str, tuple[Callable, probatio.Schema]] = {
        SERVICE_RSS_SYNC: (
            _command_handler(COMMAND_RSS_SYNC, lambda call: {}),
            SERVICE_BASE_SCHEMA,
        ),
        SERVICE_REFRESH_SERIES: (
            _command_handler(COMMAND_REFRESH_SERIES, _series_body),
            SERVICE_REFRESH_SERIES_SCHEMA,
        ),
        SERVICE_SEARCH_SERIES: (
            _command_handler(COMMAND_SERIES_SEARCH, _series_body),
            SERVICE_SEARCH_SERIES_SCHEMA,
        ),
        SERVICE_SEARCH_EPISODES: (
            _command_handler(
                COMMAND_EPISODE_SEARCH,
                lambda call: {"episodeIds": call.data[CONF_EPISODE_IDS]},
            ),
            SERVICE_SEARCH_EPISODES_SCHEMA,
        ),
        SERVICE_SEARCH_MISSING: (
            _command_handler(COMMAND_MISSING_SEARCH, lambda call: {"monitored": True}),
            SERVICE_BASE_SCHEMA,
        ),
        SERVICE_SEARCH_CUTOFF_UNMET: (
            _command_handler(COMMAND_CUTOFF_SEARCH, lambda call: {"monitored": True}),
            SERVICE_BASE_SCHEMA,
        ),
    }
    for name, (handler, schema) in command_services.items():
        hass.services.async_register(
            DOMAIN,
            name,
            handler,
            schema=schema,
            supports_response=SupportsResponse.OPTIONAL,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_QUEUE_ITEM,
        _async_remove_queue_item,
        schema=SERVICE_REMOVE_QUEUE_ITEM_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GRAB_QUEUE_ITEM,
        _async_grab_queue_item,
        schema=SERVICE_QUEUE_ITEM_SCHEMA,
    )
