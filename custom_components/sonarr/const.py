"""Constants for Sonarr."""

import logging
from typing import Final

DOMAIN: Final = "sonarr"

# Config Keys
CONF_BASE_PATH = "base_path"
CONF_DAYS = "days"
CONF_INCLUDED = "include_paths"
CONF_MORE_OPTIONS = "more_options"
CONF_UNIT = "unit"
CONF_UPCOMING_DAYS = "upcoming_days"
CONF_WANTED_MAX_ITEMS = "wanted_max_items"

# Defaults
DEFAULT_NAME = "Sonarr"
DEFAULT_UPCOMING_DAYS = 1
DEFAULT_VERIFY_SSL = False
DEFAULT_WANTED_MAX_ITEMS = 50
DEFAULT_MAX_RECORDS: Final = 20

LOGGER = logging.getLogger(__package__)

# Service names
SERVICE_GET_SERIES: Final = "get_series"
SERVICE_GET_EPISODES: Final = "get_episodes"
SERVICE_GET_QUEUE: Final = "get_queue"
SERVICE_GET_DISKSPACE: Final = "get_diskspace"
SERVICE_GET_UPCOMING: Final = "get_upcoming"
SERVICE_GET_WANTED: Final = "get_wanted"
SERVICE_GET_CUTOFF_UNMET: Final = "get_cutoff_unmet"
SERVICE_RSS_SYNC: Final = "rss_sync"
SERVICE_REFRESH_SERIES: Final = "refresh_series"
SERVICE_SEARCH_SERIES: Final = "search_series"
SERVICE_SEARCH_EPISODES: Final = "search_episodes"
SERVICE_SEARCH_MISSING: Final = "search_missing"
SERVICE_SEARCH_CUTOFF_UNMET: Final = "search_cutoff_unmet"
SERVICE_REMOVE_QUEUE_ITEM: Final = "remove_queue_item"
SERVICE_GRAB_QUEUE_ITEM: Final = "grab_queue_item"

# Service attributes
ATTR_SHOWS: Final = "shows"
ATTR_DISKS: Final = "disks"
ATTR_EPISODES: Final = "episodes"
ATTR_ENTRY_ID: Final = "entry_id"

# Sonarr command names (POST /api/v5/command)
COMMAND_RSS_SYNC: Final = "RssSync"
COMMAND_REFRESH_SERIES: Final = "RefreshSeries"
COMMAND_SERIES_SEARCH: Final = "SeriesSearch"
COMMAND_EPISODE_SEARCH: Final = "EpisodeSearch"
COMMAND_MISSING_SEARCH: Final = "MissingEpisodeSearch"
COMMAND_CUTOFF_SEARCH: Final = "CutoffUnmetEpisodeSearch"
