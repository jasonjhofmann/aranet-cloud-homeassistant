"""DataUpdateCoordinator — single shared fetch for all entities.

Polls ``measurements/last`` + ``telemetry/last`` + ``alarms/actual`` on
the configured interval and caches the sensor + base catalog less
frequently. Phase 2 wires only the measurements path; Phase 3 splits the
fast (per-poll) and slow (per-hour catalog refresh) coordinators.

The coordinator stores its output as a typed snapshot the platforms can
read without re-shaping; see :class:`AranetSnapshot`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING

from aranet_cloud import AranetAuthError, AranetCloudClient, AranetError
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

if TYPE_CHECKING:
    from aranet_cloud import Links, Reading, Sensor

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class AranetSnapshot:
    """A single coordinator-refresh result.

    Attributes:
        sensors: All sensors known to the account, keyed by numeric ID.
        readings: Latest reading per ``(sensor_id, metric_id)`` pair.
            Union of measurements/last and telemetry/last.
        links: Resolved-name helper from the most recent measurements
            response — lets entities display metric/unit names without
            an extra catalog fetch.
    """

    sensors: dict[str, Sensor] = field(default_factory=dict)
    readings: dict[tuple[str, str], Reading] = field(default_factory=dict)
    links: Links | None = None

    def reading(self, sensor_id: str, metric_id: str) -> Reading | None:
        """Look up the latest reading for a sensor+metric pair, or ``None``."""
        return self.readings.get((sensor_id, metric_id))


class AranetCoordinator(DataUpdateCoordinator[AranetSnapshot]):
    """Manages polling against Aranet Cloud."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        client: AranetCloudClient,
        scan_interval: timedelta,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=scan_interval,
        )
        self._client = client

    async def _async_update_data(self) -> AranetSnapshot:
        """Fetch a fresh snapshot from the API.

        Raises:
            ConfigEntryAuthFailed: API key revoked → triggers HA's reauth flow.
            UpdateFailed: Any other API or network failure (retried by HA).
        """
        try:
            sensors = await self._client.get_sensors()
            measurements, links = await self._client.get_measurements_last()
            telemetry, _tlinks = await self._client.get_telemetry_last()
        except AranetAuthError as err:
            # Auth failed — surface to HA's reauth machinery rather than
            # silently logging.
            raise ConfigEntryAuthFailed(str(err)) from err
        except AranetError as err:
            raise UpdateFailed(f"Aranet API error: {err}") from err

        snapshot = AranetSnapshot(
            sensors={s.id: s for s in sensors},
            readings={(r.sensor, r.metric): r for r in (*measurements, *telemetry)},
            links=links,
        )
        _LOGGER.debug(
            "Refreshed snapshot: %d sensors, %d readings",
            len(snapshot.sensors),
            len(snapshot.readings),
        )
        return snapshot
