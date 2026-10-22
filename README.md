# Sonarr (v5 API) for Home Assistant

A fork of Home Assistant's built-in [Sonarr integration](https://www.home-assistant.io/integrations/sonarr)
(core `2026.10.2`), updated for **Sonarr v5**.

It installs as a custom integration with the same `sonarr` domain, so it **replaces the
built-in one**. Existing config entries, entity IDs and dashboards carry over unchanged.

## What's different from core

**v5 API**
- Talks to `/api/v5` directly with HA's own aiohttp session. `aiopyarr` (which only
  speaks the deprecated `/api/v3`) is gone, so there are no extra requirements.
- Handles v5's grouped queue: one record per download, which can cover a whole season.
  The Queue sensor still counts *episodes*, and its attributes label season packs as
  `Show S01E01-E10`.
- Each endpoint is polled at its own rate instead of all of them every 30 s: queue 30 s,
  health and commands 1 min, calendar, wanted and disk space 5 min, series 15 min,
  status 1 h.
- Calendar events fall back to the series runtime (then 30 min) when an episode has no
  runtime yet, so they are no longer zero-length.
- Episode artwork: the Upcoming sensor has an `episodes` attribute (not recorded) listing
  each episode with its `screenshot`, plus the series `poster` and `fanart`. The
  `get_upcoming`, `get_episodes`, `get_wanted` and `get_cutoff_unmet` responses include
  `episode_images` next to the series `images`.
- The config flow rejects servers without the v5 API (Sonarr v4 or older) with a clear error.

**New entities**
| Entity | Default |
|---|---|
| `binary_sensor.sonarr_health`: on when Sonarr reports a health warning or error; issues in attributes | enabled |
| `sensor.sonarr_cutoff_unmet`: monitored episodes below the quality cutoff | disabled |
| `button.sonarr_rss_sync`, `button.sonarr_refresh_all_series`, `button.sonarr_search_missing` | enabled |
| `button.sonarr_search_cutoff_unmet` | disabled |

**New actions** (alongside the core `get_*` ones; `get_cutoff_unmet` is new too)
| Action | What it does |
|---|---|
| `sonarr.rss_sync` | RSS sync now |
| `sonarr.refresh_series` | Refresh one series (`series_id`) or all of them |
| `sonarr.search_series` | Search all missing episodes of a series |
| `sonarr.search_episodes` | Search specific `episode_ids` |
| `sonarr.search_missing` / `sonarr.search_cutoff_unmet` | Bulk searches |
| `sonarr.remove_queue_item` | Remove a download (`queue_id` from `get_queue`), with a removal method and optional blocklist and re-search |
| `sonarr.grab_queue_item` | Grab a delayed release now |

Command actions can return `{command_id, status}` as a response.

## Install

HACS → Custom repositories → `https://github.com/Luca-Bachini-Barr/ha-sonarr` (Integration),
or copy `custom_components/sonarr` into your config folder. Then restart Home Assistant.

To go back to the built-in integration, delete `custom_components/sonarr` and restart.

## License

Apache-2.0, like Home Assistant core, which this is derived from.
