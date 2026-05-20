"""Sensor platform — one entity per (sensor × active metric) across all sensor types.

Driven by :data:`METRIC_REGISTRY` — a static table that maps each Aranet
metric ID to the HA sensor attributes it should declare (device class,
state class, display precision, translation key, icon override). Adding a
new metric is a single-row change.

Base stations also get diagnostic entities (firmware version) so users can
see the gateway health at a glance.

Entity-id stability: ``unique_id`` is always ``{domain}_{sensor_serial}_{metric_id}``
or ``{domain}_base_{base_id}_{key}``. The sensor serial is the hex code
printed on the device — it survives any cloud-side rekeying.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, Metric, unit_for_id

if TYPE_CHECKING:
    from aranet_cloud import Base as AranetBase
    from aranet_cloud import Sensor as AranetSensor
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import AranetCoordinator


@dataclass(frozen=True, kw_only=True)
class AranetMetricDescription(SensorEntityDescription):
    """Static spec for an Aranet metric → HA sensor entity.

    Wraps :class:`SensorEntityDescription` with an explicit ``metric_id``
    binding so the platform can look up the right reading from the snapshot.
    """

    metric_id: str


# All currently-supported metrics. Adding a new one is one row.
# state_class defaults to MEASUREMENT (the only sensible choice for the
# current-value entities here); ``key`` becomes the entity-id suffix.
METRIC_REGISTRY: dict[str, AranetMetricDescription] = {
    Metric.TEMPERATURE: AranetMetricDescription(
        metric_id=Metric.TEMPERATURE,
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    Metric.HUMIDITY: AranetMetricDescription(
        metric_id=Metric.HUMIDITY,
        key="humidity",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    Metric.CO2: AranetMetricDescription(
        metric_id=Metric.CO2,
        key="co2",
        translation_key="co2",
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    Metric.ATMOSPHERIC_PRESSURE: AranetMetricDescription(
        metric_id=Metric.ATMOSPHERIC_PRESSURE,
        key="pressure",
        translation_key="atmospheric_pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    Metric.VOLUMETRIC_WATER_CONTENT: AranetMetricDescription(
        metric_id=Metric.VOLUMETRIC_WATER_CONTENT,
        key="soil_moisture",
        translation_key="soil_moisture",
        device_class=SensorDeviceClass.MOISTURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    # Soil electrical metrics — no clean HA device_class match. Use state_class
    # only so HA's long-term statistics still works; unit comes from the API.
    Metric.SOIL_DIELECTRIC_PERMITTIVITY: AranetMetricDescription(
        metric_id=Metric.SOIL_DIELECTRIC_PERMITTIVITY,
        key="soil_permittivity",
        translation_key="soil_permittivity",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-percent",
        suggested_display_precision=2,
    ),
    Metric.SOIL_ELECTRICAL_CONDUCTIVITY: AranetMetricDescription(
        metric_id=Metric.SOIL_ELECTRICAL_CONDUCTIVITY,
        key="soil_ec",
        translation_key="soil_ec",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:flash-triangle",
        suggested_display_precision=3,
    ),
    Metric.PORE_ELECTRICAL_CONDUCTIVITY: AranetMetricDescription(
        metric_id=Metric.PORE_ELECTRICAL_CONDUCTIVITY,
        key="pore_ec",
        translation_key="pore_ec",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-percent-alert",
        suggested_display_precision=3,
    ),
    Metric.VAPOUR_PRESSURE_DEFICIT: AranetMetricDescription(
        metric_id=Metric.VAPOUR_PRESSURE_DEFICIT,
        key="vpd",
        translation_key="vapour_pressure_deficit",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    Metric.DAY_LIGHT_INTEGRAL: AranetMetricDescription(
        metric_id=Metric.DAY_LIGHT_INTEGRAL,
        key="dli",
        translation_key="day_light_integral",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:white-balance-sunny",
        suggested_display_precision=2,
    ),
    Metric.RSSI: AranetMetricDescription(
        metric_id=Metric.RSSI,
        key="rssi",
        translation_key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
    ),
    Metric.BATTERY: AranetMetricDescription(
        metric_id=Metric.BATTERY,
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create entities for every (sensor × active metric) we know how to render."""
    coordinator: AranetCoordinator = entry.runtime_data
    snapshot = coordinator.data

    entities: list[SensorEntity] = []

    # IMPORTANT ordering: bases must be added BEFORE per-sensor entities so
    # the base devices exist by the time sensor entities reference them via
    # ``via_device``. HA deprecated the implicit-creation path; from
    # 2025.12 onwards the via_device target must already be registered.
    for base in snapshot.bases.values():
        entities.append(AranetBaseFirmwareSensor(coordinator, base))

    for sensor in snapshot.sensors.values():
        for metric_id in sensor.active_metrics:
            description = METRIC_REGISTRY.get(metric_id)
            if description is None:
                # Unknown metric → silently skip. Phase 3 contract is
                # forward-compatible with new server-side metrics.
                continue
            entities.append(AranetMetricSensor(coordinator, sensor, description))

    async_add_entities(entities)


class AranetMetricSensor(CoordinatorEntity["AranetCoordinator"], SensorEntity):
    """A measurement-or-telemetry value for one (sensor × metric)."""

    _attr_has_entity_name = True
    entity_description: AranetMetricDescription

    def __init__(
        self,
        coordinator: AranetCoordinator,
        sensor: AranetSensor,
        description: AranetMetricDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._sensor_id = sensor.id
        self._serial = sensor.serial
        self._attr_unique_id = f"{DOMAIN}_{sensor.serial}_{description.metric_id}"
        self._attr_device_info = _sensor_device_info(sensor)

    @property
    def native_value(self) -> float | None:
        """Latest reading's value, or ``None`` if no data yet."""
        reading = self.coordinator.data.reading(self._sensor_id, self.entity_description.metric_id)
        return reading.value if reading else None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Unit from the latest reading, mapped to HA's expected name.

        The unit comes from the reading itself rather than a class attribute,
        because the Aranet account's display-unit preference (°C vs °F, ppm
        vs fraction, etc.) flows through into the API response. Reflecting
        it dynamically here gives users the same units in HA as in the
        Aranet app — no surprise conversions.
        """
        reading = self.coordinator.data.reading(self._sensor_id, self.entity_description.metric_id)
        if reading is None:
            return None
        return unit_for_id(reading.unit) or None

    @property
    def available(self) -> bool:
        """Available only when the coordinator's last fetch produced a reading."""
        if not super().available:
            return False
        return (
            self.coordinator.data.reading(self._sensor_id, self.entity_description.metric_id)
            is not None
        )


class AranetBaseFirmwareSensor(CoordinatorEntity["AranetCoordinator"], SensorEntity):
    """Diagnostic entity exposing a base station's firmware version string."""

    _attr_has_entity_name = True
    _attr_translation_key = "base_firmware"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:chip"

    def __init__(self, coordinator: AranetCoordinator, base: AranetBase) -> None:
        super().__init__(coordinator)
        self._base_id = base.id
        self._attr_unique_id = f"{DOMAIN}_base_{base.id}_firmware"
        self._attr_device_info = _base_device_info(base)

    @property
    def native_value(self) -> str | None:
        base = self.coordinator.data.bases.get(self._base_id)
        return base.firmware if base else None


# ---------------------------------------------------------------------------
# DeviceInfo helpers — shared with binary_sensor.py
# ---------------------------------------------------------------------------


def _sensor_device_info(sensor: AranetSensor) -> DeviceInfo:
    """DeviceInfo for one Aranet sensor, parented to its primary base."""
    info = DeviceInfo(
        identifiers={(DOMAIN, sensor.serial)},
        name=sensor.name or f"Aranet {sensor.serial}",
        manufacturer=MANUFACTURER,
        model=sensor.type,
        serial_number=sensor.serial,
    )
    if sensor.primary_base:
        info["via_device"] = (DOMAIN, f"base_{sensor.primary_base}")
    return info


def _base_device_info(base: AranetBase) -> DeviceInfo:
    """DeviceInfo for a base station — top-level device, no via_device."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"base_{base.id}")},
        name=base.name or f"Aranet base {base.id}",
        manufacturer=MANUFACTURER,
        model=base.product or "Aranet Base",
        sw_version=base.firmware or None,
        serial_number=base.id,
    )
