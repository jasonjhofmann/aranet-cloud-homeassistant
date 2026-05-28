"""DataUpdateCoordinator — single shared fetch for all platforms.

Polls measurements/last + telemetry/last + alarms/actual on every cycle, plus
the catalog (sensors, bases) which changes much less often but is cheap to
refetch alongside. Phase 3 keeps this as a single coordinator for simplicity;
splitting into fast/slow tiers is reserved for a later perf optimisation if
ever needed.

The output snapshot is :class:`AranetSnapshot`, consumed by all platforms.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from aranet_cloud import AranetAuthError, AranetCloudClient, AranetError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

if TYPE_CHECKING:
    from aranet_cloud import Alarm, Base, Links, Reading, Sensor

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class AranetSnapshot:
    """A single coordinator-refresh result, consumed by all platforms.

    Attributes:
        sensors: All sensors known to the account, keyed by numeric ID.
        bases: Base stations, keyed by base ID.
        readings: Latest reading per ``(sensor_id, metric_id)`` pair. Union of
            measurements/last and telemetry/last so platforms can look up any
            metric without caring which endpoint produced it.
        alarms: Currently-active alarms, keyed by alarm ID.
        links: Resolved-name helper from the most recent measurements
            response. Currently informational — entities use translation
            keys instead of API-supplied names.
    """

    sensors: dict[str, Sensor] = field(default_factory=dict)
    bases: dict[str, Base] = field(default_factory=dict)
    readings: dict[tuple[str, str], Reading] = field(default_factory=dict)
    alarms: dict[str, Alarm] = field(default_factory=dict)
    links: Links | None = None

    def reading(self, sensor_id: str, metric_id: str) -> Reading | None:
        """Look up the latest reading for a sensor+metric pair, or ``None``."""
        return self.readings.get((sensor_id, metric_id))

    def active_alarm(self, sensor_id: str, metric_id: str) -> Alarm | None:
        """Return the currently-active alarm for ``(sensor, metric)``, or None.

        Aranet rules are 1:1 with metrics (each rule watches exactly one
        metric), so this is a clean lookup. If multiple alarms match (rare —
        e.g. multiple user-defined rules on the same metric), the highest-
        severity one wins.
        """
        best: Alarm | None = None
        for alarm in self.alarms.values():
            if alarm.sensor != sensor_id or alarm.metric != metric_id:
                continue
            if best is None or alarm.severity > best.severity:
                best = alarm
        return best


class AranetCoordinator(DataUpdateCoordinator[AranetSnapshot]):
    """Polls Aranet Cloud on a fixed cadence and serves a unified snapshot."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        *,
        client: AranetCloudClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
            config_entry=entry,
        )
        self._client = client

    async def _async_update_data(self) -> AranetSnapshot:
        """Fetch a fresh snapshot from the API.

        Raises:
            ConfigEntryAuthFailed: 401 from the API → triggers HA's reauth flow.
            UpdateFailed: any other API or network failure (retried by HA).
        """
        try:
            sensors = await self._client.get_sensors()
            bases = await self._client.get_bases()
            measurements, links = await self._client.get_measurements_last()
            telemetry, _tlinks = await self._client.get_telemetry_last()
            alarms = await self._client.get_alarms_actual()
        except AranetAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except AranetError as err:
            raise UpdateFailed(f"Aranet API error: {err}") from err

        snapshot = AranetSnapshot(
            sensors={s.id: s for s in sensors},
            bases={b.id: b for b in bases},
            readings={(r.sensor, r.metric): r for r in (*measurements, *telemetry)},
            alarms={a.id: a for a in alarms},
            links=links,
        )
        _LOGGER.debug(
            "Snapshot: %d sensors, %d bases, %d readings, %d active alarms",
            len(snapshot.sensors),
            len(snapshot.bases),
            len(snapshot.readings),
            len(snapshot.alarms),
        )
        return snapshot
