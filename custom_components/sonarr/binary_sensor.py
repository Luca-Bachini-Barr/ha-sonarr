"""Support for Sonarr binary sensors."""

from typing import Any, override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HealthDataUpdateCoordinator, SonarrConfigEntry
from .entity import SonarrEntity

HEALTH_TYPE = BinarySensorEntityDescription(
    key="health",
    translation_key="health",
    device_class=BinarySensorDeviceClass.PROBLEM,
    entity_category=EntityCategory.DIAGNOSTIC,
)

# Health check results that count as a problem; "notice" is informational.
PROBLEM_TYPES = ("warning", "error")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SonarrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Sonarr health binary sensor."""
    async_add_entities(
        [SonarrHealthBinarySensor(entry.runtime_data.health, HEALTH_TYPE)]
    )


class SonarrHealthBinarySensor(SonarrEntity[list[dict[str, Any]]], BinarySensorEntity):
    """On when Sonarr reports a health warning or error."""

    coordinator: HealthDataUpdateCoordinator

    @property
    @override
    def is_on(self) -> bool:
        """Return true if any health check is failing."""
        return any(c.get("type") in PROBLEM_TYPES for c in self.coordinator.data)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the failing health checks."""
        return {
            "issues": [
                {
                    "source": check.get("source"),
                    "type": check.get("type"),
                    "message": check.get("message"),
                    "wiki_url": check.get("wikiUrl"),
                }
                for check in self.coordinator.data
            ]
        }
