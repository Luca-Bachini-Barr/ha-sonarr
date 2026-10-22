"""Support for Sonarr sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import SonarrConfigEntry, SonarrDataT, SonarrDataUpdateCoordinator
from .entity import SonarrEntity
from .helpers import (
    episode_identifier,
    local_air_date,
    queue_identifier,
    queue_progress,
    series_title,
)


@dataclass(frozen=True)
class SonarrSensorEntityDescriptionMixIn(Generic[SonarrDataT]):  # noqa: UP046
    """Mixin for Sonarr sensor."""

    attributes_fn: Callable[[SonarrDataT], dict[str, Any]]
    value_fn: Callable[[SonarrDataT], StateType]


@dataclass(frozen=True, kw_only=True)
class SonarrSensorEntityDescription(
    SensorEntityDescription, SonarrSensorEntityDescriptionMixIn[SonarrDataT]
):
    """Class to describe a Sonarr sensor."""


def get_disk_space_attr(disks: list[dict[str, Any]]) -> dict[str, str]:
    """Create the attributes for disk space."""
    attrs: dict[str, str] = {}
    for disk in disks:
        free = disk.get("freeSpace", 0) / 1024**3
        total = disk.get("totalSpace", 0) / 1024**3
        usage = free / total * 100 if total else 0
        attrs[disk["path"]] = (
            f"{free:.2f}/{total:.2f}{UnitOfInformation.GIGABYTES} ({usage:.2f}%)"
        )
    return attrs


def get_queue_value(queue: dict[str, Any]) -> int:
    """Count queued episodes; a v5 record is one download that may cover several."""
    return sum(
        max(len(record.get("episodeIds") or []), 1)
        for record in queue.get("records") or []
    )


def get_queue_attr(queue: dict[str, Any]) -> dict[str, str]:
    """Create the attributes for series queue."""
    attrs: dict[str, str] = {}
    for record in queue.get("records") or []:
        name = f"{series_title(record)} {queue_identifier(record)}".strip()
        attrs[name] = f"{queue_progress(record):.2f}%"
    return attrs


def get_wanted_attr(wanted: dict[str, Any]) -> dict[str, Any]:
    """Create the attributes for missing / cutoff-unmet episodes."""
    return {
        f"{series_title(item)} {episode_identifier(item)}": local_air_date(item)
        for item in wanted.get("records") or []
    }


SENSOR_TYPES: dict[str, SonarrSensorEntityDescription[Any]] = {
    "commands": SonarrSensorEntityDescription[list[dict[str, Any]]](
        key="commands",
        translation_key="commands",
        entity_registry_enabled_default=False,
        value_fn=len,
        attributes_fn=lambda data: {c["name"]: c.get("status") for c in data},
    ),
    "diskspace": SonarrSensorEntityDescription[list[dict[str, Any]]](
        key="diskspace",
        translation_key="diskspace",
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_registry_enabled_default=False,
        value_fn=lambda data: f"{sum(d.get('freeSpace', 0) for d in data) / 1024**3:.2f}",
        attributes_fn=get_disk_space_attr,
    ),
    "queue": SonarrSensorEntityDescription[dict[str, Any]](
        key="queue",
        translation_key="queue",
        entity_registry_enabled_default=False,
        value_fn=get_queue_value,
        attributes_fn=get_queue_attr,
    ),
    "series": SonarrSensorEntityDescription[list[dict[str, Any]]](
        key="series",
        translation_key="series",
        entity_registry_enabled_default=False,
        value_fn=len,
        attributes_fn=lambda data: {
            s.get("title"): (
                f"{(s.get('statistics') or {}).get('episodeFileCount', 0)}/"
                f"{(s.get('statistics') or {}).get('episodeCount', 0)} Episodes"
            )
            for s in data
        },
    ),
    "upcoming": SonarrSensorEntityDescription[list[dict[str, Any]]](
        key="upcoming",
        translation_key="upcoming",
        value_fn=len,
        attributes_fn=lambda data: {
            series_title(e): episode_identifier(e) for e in data
        },
    ),
    "wanted": SonarrSensorEntityDescription[dict[str, Any]](
        key="wanted",
        translation_key="wanted",
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.get("totalRecords", 0),
        attributes_fn=get_wanted_attr,
    ),
    "cutoff": SonarrSensorEntityDescription[dict[str, Any]](
        key="cutoff_unmet",
        translation_key="cutoff_unmet",
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.get("totalRecords", 0),
        attributes_fn=get_wanted_attr,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SonarrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sonarr sensors based on a config entry."""
    async_add_entities(
        SonarrSensor(getattr(entry.runtime_data, coordinator_type), description)
        for coordinator_type, description in SENSOR_TYPES.items()
    )


class SonarrSensor(SonarrEntity[SonarrDataT], SensorEntity):
    """Implementation of the Sonarr sensor."""

    coordinator: SonarrDataUpdateCoordinator[SonarrDataT]
    entity_description: SonarrSensorEntityDescription[SonarrDataT]

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the entity."""
        return self.entity_description.attributes_fn(self.coordinator.data)

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
