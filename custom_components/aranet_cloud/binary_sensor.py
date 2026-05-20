"""Binary-sensor platform — surfaces the built-in Aranet alarm rules.

Two entity classes:

* :class:`AranetLowBatteryBinarySensor` — one per sensor that reports battery
  voltage (metric 62). On when there's an active "Low battery" alarm for
  that sensor. Aranet's built-in rule fires below a per-sensor-type
  threshold.
* :class:`AranetBaseOfflineBinarySensor` — one per base station. On when
  there's an active "Base station offline" alarm (metric 81).

User-defined alarm rules on other metrics aren't surfaced here yet; doing
so requires correlating the rules endpoint with the sensors that have the
matching metric. Reserved for a future revision.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, Metric
from .sensor import _base_device_info, _sensor_device_info

if TYPE_CHECKING:
    from aranet_cloud import Base as AranetBase
    from aranet_cloud import Sensor as AranetSensor
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import AranetCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create one low-battery binary_sensor per battery-reporting sensor +
    one offline binary_sensor per base."""
    coordinator: AranetCoordinator = entry.runtime_data
    snapshot = coordinator.data

    entities: list[BinarySensorEntity] = []

    for sensor in snapshot.sensors.values():
        if Metric.BATTERY in sensor.active_metrics:
            entities.append(AranetLowBatteryBinarySensor(coordinator, sensor))

    for base in snapshot.bases.values():
        entities.append(AranetBaseOfflineBinarySensor(coordinator, base))

    async_add_entities(entities)


class AranetLowBatteryBinarySensor(
    CoordinatorEntity["AranetCoordinator"], BinarySensorEntity
):
    """On when Aranet's Low battery alarm rule is firing for this sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "low_battery"
    _attr_device_class = BinarySensorDeviceClass.BATTERY

    def __init__(self, coordinator: AranetCoordinator, sensor: AranetSensor) -> None:
        super().__init__(coordinator)
        self._sensor_id = sensor.id
        self._attr_unique_id = f"{DOMAIN}_{sensor.serial}_low_battery"
        self._attr_device_info = _sensor_device_info(sensor)

    @property
    def is_on(self) -> bool:
        alarm = self.coordinator.data.active_alarm(self._sensor_id, Metric.BATTERY)
        return alarm is not None


class AranetBaseOfflineBinarySensor(
    CoordinatorEntity["AranetCoordinator"], BinarySensorEntity
):
    """On when the base station is reported offline by Aranet's built-in rule."""

    _attr_has_entity_name = True
    _attr_translation_key = "base_offline"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: AranetCoordinator, base: AranetBase) -> None:
        super().__init__(coordinator)
        self._base_id = base.id
        self._attr_unique_id = f"{DOMAIN}_base_{base.id}_offline"
        self._attr_device_info = _base_device_info(base)

    @property
    def is_on(self) -> bool:
        # The base-station-offline rule's "sensor" field is the base ID.
        alarm = self.coordinator.data.active_alarm(self._base_id, Metric.BASE_STATUS)
        # BinarySensorDeviceClass.CONNECTIVITY semantics: on = connected.
        # The alarm fires when OFFLINE, so we invert.
        return alarm is None
