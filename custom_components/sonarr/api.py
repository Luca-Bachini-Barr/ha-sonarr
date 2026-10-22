"""Minimal async client for the Sonarr v5 API."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import aiohttp

API_PATH = "/api/v5"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


class SonarrError(Exception):
    """Base Sonarr API error."""


class SonarrConnectionError(SonarrError):
    """Sonarr could not be reached."""


class SonarrAuthenticationError(SonarrError):
    """The API key was rejected."""


class SonarrUnsupportedVersionError(SonarrError):
    """The server does not expose the v5 API (Sonarr v4 or older)."""


def _iso(value: datetime) -> str:
    """Format a datetime the way Sonarr expects in query strings."""
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


class SonarrClient:
    """Talk to Sonarr's /api/v5 endpoints."""

    def __init__(self, session: aiohttp.ClientSession, url: str, api_key: str) -> None:
        """Initialize the client."""
        self._session = session
        self.base_url = url.rstrip("/")
        self._headers = {"X-Api-Key": api_key, "Accept": "application/json"}

    async def _request(
        self,
        method: str,
        path: str,
        params: list[tuple[str, Any]] | None = None,
        json: Any = None,
    ) -> Any:
        """Send a request and return the decoded JSON body."""
        query = [
            (key, str(value).lower() if isinstance(value, bool) else str(value))
            for key, value in params or []
        ]
        try:
            async with self._session.request(
                method,
                f"{self.base_url}{API_PATH}/{path}",
                params=query,
                json=json,
                headers=self._headers,
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                if resp.status in (401, 403):
                    raise SonarrAuthenticationError("Invalid API key")
                if resp.status == 404 and path == "system/status":
                    raise SonarrUnsupportedVersionError(
                        "Sonarr v5 API not found at this URL"
                    )
                if resp.status >= 400:
                    body = await resp.text()
                    raise SonarrError(f"HTTP {resp.status} from {path}: {body[:200]}")
                if resp.status == 204 or resp.content_length == 0:
                    return None
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise SonarrConnectionError(f"Error talking to Sonarr: {err}") from err

    async def get_system_status(self) -> dict[str, Any]:
        """Return /system/status."""
        return await self._request("GET", "system/status")

    async def get_health(self) -> list[dict[str, Any]]:
        """Return the active health checks."""
        return await self._request("GET", "health")

    async def get_calendar(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        """Return episodes airing between start and end, with their series."""
        return await self._request(
            "GET",
            "calendar",
            [
                ("start", _iso(start)),
                ("end", _iso(end)),
                ("includeSubresources", "series"),
                ("includeSubresources", "images"),
            ],
        )

    async def get_commands(self) -> list[dict[str, Any]]:
        """Return recent and running commands."""
        return await self._request("GET", "command")

    async def get_diskspace(self) -> list[dict[str, Any]]:
        """Return disk space for every mapped path."""
        return await self._request("GET", "diskspace")

    async def get_queue(self, page_size: int = 1000) -> dict[str, Any]:
        """Return the download queue, one record per download."""
        return await self._request(
            "GET",
            "queue",
            [
                ("pageSize", page_size),
                ("includeSubresources", "series"),
                ("includeSubresources", "episodes"),
            ],
        )

    async def get_series(self) -> list[dict[str, Any]]:
        """Return every series with statistics."""
        return await self._request("GET", "series")

    async def get_episodes(
        self, series_id: int, season_number: int | None = None
    ) -> list[dict[str, Any]]:
        """Return the episodes of a series."""
        params: list[tuple[str, Any]] = [
            ("seriesId", series_id),
            ("includeSubresources", "images"),
        ]
        if season_number is not None:
            params.append(("seasonNumber", season_number))
        return await self._request("GET", "episode", params)

    async def _get_wanted(self, kind: str, page_size: int) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"wanted/{kind}",
            [
                ("pageSize", page_size),
                ("monitored", True),
                ("sortKey", "episodes.airDateUtc"),
                ("sortDirection", "descending"),
                ("includeSubresources", "series"),
                ("includeSubresources", "images"),
            ],
        )

    async def get_wanted_missing(self, page_size: int) -> dict[str, Any]:
        """Return monitored episodes that have aired but have no file."""
        return await self._get_wanted("missing", page_size)

    async def get_wanted_cutoff(self, page_size: int) -> dict[str, Any]:
        """Return monitored episodes whose file is below the quality cutoff."""
        return await self._get_wanted("cutoff", page_size)

    async def run_command(self, name: str, **body: Any) -> dict[str, Any]:
        """Queue a Sonarr command such as RssSync or MissingEpisodeSearch."""
        return await self._request("POST", "command", json={"name": name, **body})

    async def remove_queue_item(
        self,
        queue_id: int,
        removal_method: str = "removeFromClient",
        blocklist_method: str = "doNotBlocklist",
    ) -> None:
        """Remove a download from the queue."""
        await self._request(
            "DELETE",
            f"queue/{queue_id}",
            [("removalMethod", removal_method), ("blocklistMethod", blocklist_method)],
        )

    async def grab_queue_item(self, queue_id: int) -> None:
        """Force-grab a pending (delayed) release."""
        await self._request("POST", f"queue/grab/{queue_id}")
