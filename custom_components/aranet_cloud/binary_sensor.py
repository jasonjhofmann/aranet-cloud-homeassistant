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

import logging
from functools import partial
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, Metric
from .sensor import READING_MAX_AGE, _base_device_info, _sensor_device_info

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from aranet_cloud import Base as AranetBase
    from aranet_cloud import Sensor as AranetSensor

    from .coordinator import AranetCoordinator

# Coordinator-backed, read-only entities — no per-entity update fan-out.
# 0 = unlimited (the coordinator already serialises the single fetch).
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create alarm binary_sensors, adding more as sensors/bases appear."""
    coordinator: AranetCoordinator = entry.runtime_data
    # Per-entity keys whose entity object currently exists in HA. As in
    # sensor.py: a key is discarded only when the entity is actually removed
    # (stale-device prune, or an aborted add), never on mere metric
    # deactivation — re-activation must not re-add an existing unique_id.
    known: set[str] = set()

    def _track(entity: BinarySensorEntity, key: str) -> BinarySensorEntity:
        """Mark ``key`` as known until its entity actually leaves HA."""
        known.add(key)
        entity.async_on_remove(partial(known.discard, key))
        return entity

    @callback
    def _add_entities() -> None:
        snapshot = coordinator.data
        new_entities: list[BinarySensorEntity] = []

        for sensor in snapshot.sensors.values():
            if Metric.BATTERY not in sensor.active_metrics:
                continue
            key = f"low_battery_{sensor.serial}"
            if key not in known:
                new_entities.append(
                    _track(AranetLowBatteryBinarySensor(coordinator, sensor), key)
                )

        for base in snapshot.bases.values():
            key = f"offline_{base.id}"
            if key not in known:
                new_entities.append(
                    _track(AranetBaseOfflineBinarySensor(coordinator, base), key)
                )

        if new_entities:
            _LOGGER.debug(
                "Adding %d binary_sensor entit%s: %s",
                len(new_entities),
                "y" if len(new_entities) == 1 else "ies",
                ", ".join(sorted(e.unique_id for e in new_entities if e.unique_id)),
            )
            async_add_entities(new_entities)

    _add_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_entities))


class AranetLowBatteryBinarySensor(
    CoordinatorEntity["AranetCoordinator"], BinarySensorEntity
):
    """On when Aranet's Low battery alarm rule is firing for this sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "low_battery"
    _attr_device_class = BinarySensorDeviceClass.BATTERY

    def __init__(self, coordinator: AranetCoordinator, sensor: AranetSensor) -> None:
        super().__init__(coordinator)
        # Bind the permanent serial, not the cloud-numeric ID — the latter
        # changes if the sensor is deleted and re-added in the cloud.
        self._serial = sensor.serial
        self._attr_unique_id = f"{DOMAIN}_{sensor.serial}_low_battery"
        self._attr_device_info = _sensor_device_info(sensor)

    @property
    def is_on(self) -> bool:
        alarm = self.coordinator.data.active_alarm_for_serial(
            self._serial, Metric.BATTERY
        )
        return alarm is not None

    @property
    def available(self) -> bool:
        """Tied to the underlying battery reading's staleness.

        The alarm feed itself carries no timestamp for the *absence* of an
        alarm, but the sensor's battery telemetry does: a battery reading
        older than :data:`READING_MAX_AGE` means the sensor has stopped
        reporting, so neither "low battery" nor "battery fine" can be
        vouched for — same staleness pattern as the metric sensors. With no
        reading or no timestamp the alarm feed (refreshed every poll) gets
        the benefit of the doubt.

        A live alarm always wins, though. An actively-firing low-battery
        alarm is itself fresh evidence (the alarm feed is refetched every
        poll), so it must never be masked as ``unavailable`` behind a stale
        battery reading — that hides the very alert this entity exists to
        raise. This is the dying-battery endgame: the sensor's last telemetry
        can predate the alarm's propagation, so the reading is already stale
        when the alarm appears. Surface it (``is_on`` → on) rather than
        swallowing it.
        """
        if not super().available:
            return False
        if (
            self.coordinator.data.active_alarm_for_serial(self._serial, Metric.BATTERY)
            is not None
        ):
            return True
        reading = self.coordinator.data.reading_for_serial(self._serial, Metric.BATTERY)
        if reading is None or reading.time is None:
            return True
        return (dt_util.utcnow() - reading.time) <= READING_MAX_AGE


class AranetBaseOfflineBinarySensor(
    CoordinatorEntity["AranetCoordinator"], BinarySensorEntity
):
    """Base-station connectivity (CONNECTIVITY class, on = connected).

    On (connected) while the base is checking in; off (disconnected) when
    Aranet's built-in offline rule is firing OR the base has gone dark
    (``Base.last_seen`` past :data:`READING_MAX_AGE`). The built-in rule
    fires when the base is OFFLINE, so :meth:`is_on` inverts it.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "base_offline"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: AranetCoordinator, base: AranetBase) -> None:
        super().__init__(coordinator)
        self._base_id = base.id
        self._attr_unique_id = f"{DOMAIN}_base_{base.id}_offline"
        self._attr_device_info = _base_device_info(base)

    @property
    def available(self) -> bool:
        """Available only while the base is present in the current snapshot.

        Deliberately NOT gated on ``Base.last_seen`` staleness (unlike
        AranetBaseFirmwareSensor): a stale last_seen is precisely the
        condition this entity exists to report — while the base is dark the
        cloud keeps asserting "Disconnected", and going unavailable would
        mask it (``is_on`` reports it instead).

        It IS gated on base *presence*, though. If the base vanishes from the
        snapshot — prune grace after account removal, or a transient
        ``bases=[]`` cloud hiccup — its per-base offline alarm vanishes with
        it, so ``is_on`` would otherwise fabricate on/"connected" for a base
        we no longer have any data for: a false recovery/all-clear on a base
        station that is actually gone. Report unavailable there instead.
        """
        if not super().available:
            return False
        return self._base_id in self.coordinator.data.bases

    @property
    def is_on(self) -> bool:
        # The base-station-offline rule's "sensor" field is the base ID.
        # BinarySensorDeviceClass.CONNECTIVITY semantics: on = connected.
        alarm = self.coordinator.data.active_alarm(self._base_id, Metric.BASE_STATUS)
        if alarm is not None:
            # Aranet's built-in offline rule is firing → disconnected.
            return False
        # No offline alarm: fall back to the base's own check-in time so a
        # demonstrably-dark base (last_seen past READING_MAX_AGE) cannot
        # assert "connected" merely because the cloud hasn't raised — or the
        # account never configured — the offline rule. ``available`` has
        # already guaranteed the base is present in the snapshot here; a
        # missing timestamp gets the same benefit of the doubt as elsewhere.
        base = self.coordinator.data.bases.get(self._base_id)
        if base is None or base.last_seen is None:
            return True
        return (dt_util.utcnow() - base.last_seen) <= READING_MAX_AGE
