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

import logging
from dataclasses import dataclass
from datetime import timedelta
from functools import partial
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.sensor.const import DEVICE_CLASS_UNITS
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, MANUFACTURER, Metric, unit_for_id

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from aranet_cloud import Base as AranetBase
    from aranet_cloud import Reading
    from aranet_cloud import Sensor as AranetSensor

    from .coordinator import AranetCoordinator

# All entities read from the shared DataUpdateCoordinator and never write
# upstream, so there is no per-entity update fan-out to throttle.
# 0 = unlimited (the coordinator already serialises the single fetch).
PARALLEL_UPDATES = 0

# Staleness threshold for entity availability. Aranet sensors transmit to
# the base at a configurable interval of 1/2/5/10 minutes (10 min is the
# coarsest the hardware offers); 2x that cadence gives a missed-cycle margin
# while still flagging a dead sensor within ~20 minutes instead of reporting
# its last value as live forever.
READING_MAX_AGE = timedelta(minutes=20)

# When the registry's declared device class is invalid for the unit actually
# delivered by the account's display preferences, prefer one of these
# unit-keyed classes over dropping the class entirely (e.g. battery voltage
# telemetry in V is a perfectly good VOLTAGE sensor, just not a BATTERY %).
_DEVICE_CLASS_BY_UNIT: dict[str, SensorDeviceClass] = {
    "V": SensorDeviceClass.VOLTAGE,
    "mV": SensorDeviceClass.VOLTAGE,
}


def _effective_device_class(
    declared: SensorDeviceClass | None, unit: str | None
) -> SensorDeviceClass | None:
    """Validate ``declared`` against the reading's actual unit.

    Aranet account display preferences flow into the API response, so the
    same metric can arrive in units HA's device classes don't accept
    (``%RH`` for HUMIDITY, ``atm`` for ATMOSPHERIC_PRESSURE, ``V`` for
    BATTERY, ``dBW`` for SIGNAL_STRENGTH, fractions for MOISTURE, ...).
    Emitting such a combo is a per-entity error in HA and breaks long-term
    statistics. Resolution order:

    1. ``declared`` if the unit is acceptable for it (or HA imposes no
       unit restriction on that class),
    2. a better-fitting class from :data:`_DEVICE_CLASS_BY_UNIT`,
    3. no device class at all (plain measurement sensor).
    """
    if declared is not None:
        allowed = DEVICE_CLASS_UNITS.get(declared)
        if allowed is None or unit in allowed:
            return declared
    if unit is not None:
        better = _DEVICE_CLASS_BY_UNIT.get(unit)
        if better is not None and unit in DEVICE_CLASS_UNITS.get(better, set()):
            return better
    return None


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
        suggested_display_precision=2,
    ),
    Metric.SOIL_ELECTRICAL_CONDUCTIVITY: AranetMetricDescription(
        metric_id=Metric.SOIL_ELECTRICAL_CONDUCTIVITY,
        key="soil_ec",
        translation_key="soil_ec",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    Metric.PORE_ELECTRICAL_CONDUCTIVITY: AranetMetricDescription(
        metric_id=Metric.PORE_ELECTRICAL_CONDUCTIVITY,
        key="pore_ec",
        translation_key="pore_ec",
        state_class=SensorStateClass.MEASUREMENT,
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
        suggested_display_precision=2,
    ),
    Metric.RSSI: AranetMetricDescription(
        metric_id=Metric.RSSI,
        key="rssi",
        translation_key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        # Niche diagnostic — off by default to keep dashboards uncluttered.
        entity_registry_enabled_default=False,
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
    # --- Additional Aranet Cloud catalog metrics (HAR-verified 2026-06-09) ---
    # These appear on specialty / Pro / transmitter sensors. Declared device
    # classes are additionally validated per-reading against the delivered
    # unit (see _effective_device_class) — an account preference for a unit
    # HA doesn't accept downgrades the class at runtime instead of emitting
    # an invalid combo.
    Metric.VOLTAGE: AranetMetricDescription(
        metric_id=Metric.VOLTAGE,
        key="voltage",
        translation_key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,  # units V, mV — both HA-valid
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    Metric.WEIGHT: AranetMetricDescription(
        metric_id=Metric.WEIGHT,
        key="weight",
        translation_key="weight",
        device_class=SensorDeviceClass.WEIGHT,  # units kg, lb — both HA-valid
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    # Distance carries a "mil" (thou) unit option that HA's distance device
    # class doesn't recognise, so no device_class — plain measurement sensor.
    Metric.DISTANCE: AranetMetricDescription(
        metric_id=Metric.DISTANCE,
        key="distance",
        translation_key="distance",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    # Differential pressure carries "mmH₂O", not an HA pressure unit → no
    # device_class.
    Metric.DIFFERENTIAL_PRESSURE: AranetMetricDescription(
        metric_id=Metric.DIFFERENTIAL_PRESSURE,
        key="differential_pressure",
        translation_key="differential_pressure",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    # Radon has no HA device class (mirrors the built-in BLE aranet integration:
    # Bq/m³ + MEASUREMENT, no device_class).
    Metric.RADON: AranetMetricDescription(
        metric_id=Metric.RADON,
        key="radon",
        translation_key="radon",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    # Fraction — dimensionless ratio, no device class or fixed unit.
    Metric.FRACTION: AranetMetricDescription(
        metric_id=Metric.FRACTION,
        key="fraction",
        translation_key="fraction",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create sensor entities, adding more as new sensors appear (dynamic-devices)."""
    coordinator: AranetCoordinator = entry.runtime_data
    # Per-entity keys whose entity object currently exists in HA. A key is
    # added when the entity is created and discarded only when the entity is
    # actually removed (stale-device prune, or an aborted add) — NOT when its
    # skill merely flips inactive. A deactivated metric keeps its entity and
    # its key, so a later re-activation doesn't call async_add_entities again
    # with an already-registered unique_id ("ID … already exists" registry
    # errors on every occurrence).
    known: set[str] = set()
    # Remembers which (sensor, metric) skips we've already logged, so the
    # debug line below fires once rather than every coordinator cycle.
    logged_skips: set[str] = set()

    def _track(entity: SensorEntity, key: str) -> SensorEntity:
        """Mark ``key`` as known until its entity actually leaves HA.

        ``async_on_remove`` also fires when an add is aborted, so a failed
        add frees the key for a retry on the next refresh.
        """
        known.add(key)
        entity.async_on_remove(partial(known.discard, key))
        return entity

    @callback
    def _add_entities() -> None:
        snapshot = coordinator.data
        new_entities: list[SensorEntity] = []

        # Bases first: their devices back the ``via_device`` link of the
        # per-sensor entities below (the device itself is registered in
        # __init__'s device sync, which runs ahead of this listener).
        for base in snapshot.bases.values():
            key = f"base_{base.id}"
            if key not in known:
                new_entities.append(
                    _track(AranetBaseFirmwareSensor(coordinator, base), key)
                )

        for sensor in snapshot.sensors.values():
            for metric_id in sensor.active_metrics:
                description = METRIC_REGISTRY.get(metric_id)
                if description is None:
                    # Metric we don't render yet → skip (forward-compatible with
                    # new Aranet metrics). Log once so it's discoverable: the
                    # fix is a one-row addition to METRIC_REGISTRY.
                    skip_key = f"{sensor.serial}_{metric_id}"
                    if skip_key not in logged_skips:
                        logged_skips.add(skip_key)
                        _LOGGER.debug(
                            "Sensor %s reports metric id %s, which this "
                            "integration doesn't render yet — skipping",
                            sensor.serial,
                            metric_id,
                        )
                    continue
                key = f"{sensor.serial}_{metric_id}"
                if key not in known:
                    new_entities.append(
                        _track(
                            AranetMetricSensor(coordinator, sensor, description), key
                        )
                    )

        if new_entities:
            _LOGGER.debug(
                "Adding %d sensor entit%s: %s",
                len(new_entities),
                "y" if len(new_entities) == 1 else "ies",
                ", ".join(sorted(e.unique_id for e in new_entities if e.unique_id)),
            )
            async_add_entities(new_entities)

    _add_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_entities))


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
        # Only the permanent hex serial is bound at construction. The cloud-
        # numeric sensor ID is resolved through the snapshot on every lookup
        # (it changes if the sensor is deleted and re-added in the cloud).
        self._serial = sensor.serial
        self._attr_unique_id = f"{DOMAIN}_{sensor.serial}_{description.metric_id}"
        self._attr_device_info = _sensor_device_info(sensor)

    def _reading(self) -> Reading | None:
        """Current reading for this entity, resolved via the serial."""
        return self.coordinator.data.reading_for_serial(
            self._serial, self.entity_description.metric_id
        )

    @property
    def native_value(self) -> float | None:
        """Latest reading's value, or ``None`` if no data yet.

        Since aranet-cloud 0.2.0, ``Reading.value`` is ``float | None`` —
        the API can report ``null`` (or unparseable) values, which the
        library no longer coerces to ``0.0``. A ``None`` value passes
        through here so HA shows *unknown* instead of a fabricated zero.
        """
        reading = self._reading()
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
        reading = self._reading()
        if reading is None:
            return None
        return unit_for_id(reading.unit) or None

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Declared device class, validated against the delivered unit.

        See :func:`_effective_device_class` — account display preferences
        can deliver units the declared class doesn't accept.
        """
        reading = self._reading()
        if reading is None:
            return self.entity_description.device_class
        return _effective_device_class(
            self.entity_description.device_class, unit_for_id(reading.unit) or None
        )

    @property
    def available(self) -> bool:
        """Available when the last fetch produced a reading that is fresh.

        A reading older than :data:`READING_MAX_AGE` means the physical
        sensor has stopped reporting (dead battery, out of range) even
        though the cloud keeps serving its last value — surface that as
        unavailable rather than presenting stale data as live. Readings
        without a timestamp are given the benefit of the doubt.
        """
        if not super().available:
            return False
        reading = self._reading()
        if reading is None:
            return False
        if reading.time is None:
            return True
        return (dt_util.utcnow() - reading.time) <= READING_MAX_AGE


class AranetBaseFirmwareSensor(CoordinatorEntity["AranetCoordinator"], SensorEntity):
    """Diagnostic entity exposing a base station's firmware version string."""

    _attr_has_entity_name = True
    _attr_translation_key = "base_firmware"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: AranetCoordinator, base: AranetBase) -> None:
        super().__init__(coordinator)
        self._base_id = base.id
        self._attr_unique_id = f"{DOMAIN}_base_{base.id}_firmware"
        self._attr_device_info = _base_device_info(base)

    @property
    def native_value(self) -> str | None:
        base = self.coordinator.data.bases.get(self._base_id)
        return base.firmware if base else None

    @property
    def available(self) -> bool:
        """Available while the base keeps checking in with the cloud.

        ``Base.last_seen`` is the cloud's record of the gateway's last
        check-in. Older than :data:`READING_MAX_AGE` means the base is dark
        (power/network down) and its data is no longer live — same staleness
        pattern as the metric sensors. A base without a ``last_seen``
        timestamp is given the benefit of the doubt.
        """
        if not super().available:
            return False
        base = self.coordinator.data.bases.get(self._base_id)
        if base is None:
            return False
        if base.last_seen is None:
            return True
        return (dt_util.utcnow() - base.last_seen) <= READING_MAX_AGE


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
