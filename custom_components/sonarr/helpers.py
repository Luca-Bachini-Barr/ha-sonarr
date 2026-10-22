"""Helper functions for Sonarr (v5 API payloads)."""

from typing import Any

from homeassistant.util import dt as dt_util


def episode_identifier(episode: dict[str, Any]) -> str:
    """Return SxxEyy for an episode."""
    return f"S{episode.get('seasonNumber', 0):02d}E{episode.get('episodeNumber', 0):02d}"


def queue_identifier(record: dict[str, Any]) -> str:
    """Return a label for a v5 queue record, which can cover several episodes."""
    episodes = sorted(
        record.get("episodes") or [],
        key=lambda e: (e.get("seasonNumber", 0), e.get("episodeNumber", 0)),
    )
    if len(episodes) == 1:
        return episode_identifier(episodes[0])
    if episodes:
        first, last = episodes[0], episodes[-1]
        if first.get("seasonNumber") == last.get("seasonNumber"):
            return f"{episode_identifier(first)}-E{last.get('episodeNumber', 0):02d}"
        return f"{episode_identifier(first)}-{episode_identifier(last)}"
    seasons = sorted(record.get("seasonNumbers") or [])
    if seasons:
        return "-".join(f"S{s:02d}" for s in (seasons[0], seasons[-1]) if s is not None)
    return ""


def queue_progress(record: dict[str, Any]) -> float:
    """Return download progress in percent."""
    size = record.get("size") or 0
    if not size:
        return 0.0
    return 100 * (1 - (record.get("sizeLeft") or 0) / size)


def series_title(item: dict[str, Any]) -> str:
    """Return the series title of a v5 record, or its own title."""
    return (item.get("series") or {}).get("title") or item.get("title") or "Unknown"


def local_air_date(item: dict[str, Any]) -> str | None:
    """Return an episode's air date in local time as ISO 8601."""
    if not (aired := item.get("airDateUtc")):
        return None
    if (parsed := dt_util.parse_datetime(aired)) is None:
        return None
    return dt_util.as_local(parsed).isoformat()


def _format_images(images: list[dict[str, Any]] | None, base_url: str | None) -> dict[str, str]:
    """Map cover type to URL, preferring the public remote URL."""
    result: dict[str, str] = {}
    for image in images or []:
        cover_type = image.get("coverType")
        if not cover_type:
            continue
        if remote_url := image.get("remoteUrl"):
            result[cover_type] = remote_url
        elif base_url and (url := image.get("url")):
            result[cover_type] = f"{base_url.rstrip('/')}{url}"
    return result


def _series_info(series: dict[str, Any] | None, base_url: str | None) -> dict[str, Any]:
    if not series:
        return {}
    return {
        "series_title": series.get("title"),
        "series_year": series.get("year"),
        "series_tvdb_id": series.get("tvdbId"),
        "series_imdb_id": series.get("imdbId"),
        "series_status": series.get("status"),
        "network": series.get("network"),
        "images": _format_images(series.get("images"), base_url),
    }


def format_queue_item(record: dict[str, Any], base_url: str | None = None) -> dict[str, Any]:
    """Format a single queue record."""
    episodes = record.get("episodes") or []
    quality = (record.get("quality") or {}).get("quality") or {}
    result: dict[str, Any] = {
        "id": record.get("id"),
        "series_id": record.get("seriesId"),
        "episode_ids": record.get("episodeIds") or [],
        "season_numbers": record.get("seasonNumbers") or [],
        "title": series_title(record),
        "download_title": record.get("title"),
        "episode_identifier": queue_identifier(record),
        "episode_count": len(episodes) or len(record.get("episodeIds") or []),
        "is_season_pack": len(episodes) > 1 or bool(record.get("isFullSeason")),
        "is_full_season": bool(record.get("isFullSeason")),
        "progress": f"{queue_progress(record):.2f}%",
        "size": record.get("size"),
        "size_left": record.get("sizeLeft"),
        "status": record.get("status"),
        "tracked_download_status": record.get("trackedDownloadStatus"),
        "tracked_download_state": record.get("trackedDownloadState"),
        "status_messages": [
            msg
            for status in record.get("statusMessages") or []
            for msg in status.get("messages") or []
        ],
        "error_message": record.get("errorMessage"),
        "download_client": record.get("downloadClient"),
        "download_id": record.get("downloadId"),
        "indexer": record.get("indexer"),
        "protocol": record.get("protocol"),
        "estimated_completion_time": record.get("estimatedCompletionTime"),
        "time_left": record.get("timeLeft"),
        "added": record.get("added"),
        "quality": quality.get("name"),
        "languages": [lang.get("name") for lang in record.get("languages") or []],
        "custom_format_score": record.get("customFormatScore"),
        "images": _format_images((record.get("series") or {}).get("images"), base_url),
    }
    if len(episodes) == 1:
        result["episode_number"] = episodes[0].get("episodeNumber")
        result["episode_title"] = episodes[0].get("title")
    return result


def format_queue(queue: dict[str, Any], base_url: str | None = None) -> dict[str, dict[str, Any]]:
    """Format queue for service response, keyed by download title."""
    return {
        record.get("title") or str(record.get("id")): format_queue_item(record, base_url)
        for record in queue.get("records") or []
    }


def format_series(
    series_list: list[dict[str, Any]], base_url: str | None = None
) -> dict[str, dict[str, Any]]:
    """Format series list for service response."""
    formatted_shows = {}
    for series in series_list:
        stats = series.get("statistics") or {}
        file_count = stats.get("episodeFileCount")
        episode_count = stats.get("episodeCount")
        formatted_shows[series.get("title")] = {
            "id": series.get("id"),
            "year": series.get("year"),
            "tvdb_id": series.get("tvdbId"),
            "imdb_id": series.get("imdbId"),
            "status": series.get("status"),
            "monitored": series.get("monitored"),
            "network": series.get("network"),
            "next_airing": series.get("nextAiring"),
            "previous_airing": series.get("previousAiring"),
            "season_count": stats.get("seasonCount"),
            "episode_file_count": file_count,
            "episode_count": episode_count,
            "size_on_disk": stats.get("sizeOnDisk"),
            "percent_of_episodes": stats.get("percentOfEpisodes"),
            "episodes_info": (
                f"{file_count}/{episode_count} Episodes"
                if file_count is not None and episode_count is not None
                else None
            ),
            "images": _format_images(series.get("images"), base_url),
        }
    return formatted_shows


# Space unit conversion factors (divisors from bytes)
SPACE_UNITS: dict[str, int] = {
    "bytes": 1,
    "kb": 1000,
    "kib": 1024,
    "mb": 1000**2,
    "mib": 1024**2,
    "gb": 1000**3,
    "gib": 1024**3,
    "tb": 1000**4,
    "tib": 1024**4,
    "pb": 1000**5,
    "pib": 1024**5,
}


def format_diskspace(
    disks: list[dict[str, Any]], space_unit: str = "bytes"
) -> dict[str, dict[str, Any]]:
    """Format diskspace for service response, keyed by path."""
    divisor = SPACE_UNITS.get(space_unit.lower(), 1)
    return {
        disk["path"]: {
            "path": disk["path"],
            "label": disk.get("label") or "",
            "free_space": disk.get("freeSpace", 0) / divisor,
            "total_space": disk.get("totalSpace", 0) / divisor,
            "unit": space_unit,
        }
        for disk in disks
    }


def format_episode(episode: dict[str, Any], base_url: str | None = None) -> dict[str, Any]:
    """Format a single episode."""
    result: dict[str, Any] = {
        "id": episode.get("id"),
        "series_id": episode.get("seriesId"),
        "tvdb_id": episode.get("tvdbId"),
        "season_number": episode.get("seasonNumber"),
        "episode_number": episode.get("episodeNumber"),
        "episode_identifier": episode_identifier(episode),
        "title": episode.get("title"),
        "air_date": episode.get("airDate"),
        "air_date_utc": episode.get("airDateUtc"),
        "overview": episode.get("overview"),
        "has_file": episode.get("hasFile", False),
        "monitored": episode.get("monitored", False),
        "runtime": episode.get("runtime"),
        "episode_file_id": episode.get("episodeFileId"),
        "finale_type": episode.get("finaleType"),
        "last_search_time": episode.get("lastSearchTime"),
    }
    result.update(_series_info(episode.get("series"), base_url))
    return result


def format_episode_list(
    episodes: list[dict[str, Any]], base_url: str | None = None
) -> dict[str, dict[str, Any]]:
    """Format episodes keyed by "Series SxxEyy"."""
    return {
        f"{series_title(e)} {episode_identifier(e)}": format_episode(e, base_url)
        for e in episodes
    }


def format_episodes(
    episodes: list[dict[str, Any]], season_number: int | None = None
) -> dict[str, dict[str, Any]]:
    """Format a series' episodes keyed by SxxEyy, optionally for one season."""
    return {
        episode_identifier(e): format_episode(e)
        for e in episodes
        if season_number is None or e.get("seasonNumber") == season_number
    }
