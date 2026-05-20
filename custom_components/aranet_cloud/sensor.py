"""Sensor platform — Phase 2: CO₂ only.

One ``sensor.aranet_*_co2`` entity per Aranet sensor that has the CO₂
skill (metric ``"3"``). Phase 3 expands to the full metric set with a
per-metric description table.

Entity-id stability: ``unique_id`` uses the device-printed hex serial
(``Sensor.serial``, e.g. ``02D0C``), NOT the cloud numeric ID. The serial
survives any cloud-side rekeying and matches what's on the device label.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import CONCENTRATION_PARTS_PER_MILLION
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, Metric

if TYPE_CHECKING:
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
    """Create one CO₂ entity per CO₂-capable sensor in the snapshot."""
    coordinator: AranetCoordinator = entry.runtime_data
    snapshot = coordinator.data

    entities: list[AranetCO2Sensor] = [
        AranetCO2Sensor(coordinator, sensor)
        for sensor in snapshot.sensors.values()
        if Metric.CO2 in sensor.active_metrics
    ]
    async_add_entities(entities)


class AranetCO2Sensor(CoordinatorEntity["AranetCoordinator"], SensorEntity):
    """CO₂ concentration from one Aranet sensor.

    Phase 2 scope: this is the *only* entity class. Phase 3 will replace
    this with a generic ``AranetMetricSensor`` table-driven by metric ID,
    inheriting device_class / state_class / unit per-metric.
    """

    _attr_device_class = SensorDeviceClass.CO2
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION
    _attr_has_entity_name = True
    _attr_translation_key = "co2"

    def __init__(self, coordinator: AranetCoordinator, sensor: AranetSensor) -> None:
        super().__init__(coordinator)
        self._sensor_id = sensor.id
        self._sensor_serial = sensor.serial
        self._attr_unique_id = f"{DOMAIN}_{sensor.serial}_{Metric.CO2}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sensor.serial)},
            name=sensor.name or f"Aranet {sensor.serial}",
            manufacturer=MANUFACTURER,
            model=sensor.type,
            serial_number=sensor.serial,
        )

    @property
    def native_value(self) -> float | None:
        """Latest CO₂ reading in ppm, or ``None`` if no data yet."""
        reading = self.coordinator.data.reading(self._sensor_id, Metric.CO2)
        return reading.value if reading else None

    @property
    def available(self) -> bool:
        """Available only when the coordinator has data AND a reading exists."""
        if not super().available:
            return False
        return self.coordinator.data.reading(self._sensor_id, Metric.CO2) is not None
