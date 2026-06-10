"""Diagnostics platform — sanitised "Download diagnostics" snapshot.

Produces a JSON dump suitable for pasting into a GitHub issue. Includes:

* Account context: scan interval, number of sensors / bases / active alarms
* Sensor + base catalog (full metadata)
* Latest reading per (sensor × metric)
* Active alarms

Redacts: the API key and the salted-hash unique_id (which is derived from
the key). Everything else is non-sensitive metadata about the user's setup.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import AranetCoordinator

# Keys redacted at any depth. Beyond what the dump contains today, this
# pre-lists sensitive keys from Aranet Cloud's RAW API payloads (inventoried
# from the aranet-cloud client's parsers) that we never include today but
# would need scrubbing if a future revision attached a raw payload or
# request context to the dump. Unused keys cost nothing.
REDACT = {
    # Present in today's dump
    CONF_API_KEY,
    "unique_id",
    # Raw-payload keys (hypothetical future inclusion)
    "location",  # free-text sensor placement
    "region",  # account region
    "note",
    "notes",  # user free-text can contain anything
    # Request context (hypothetical future inclusion)
    "Authorization",
    "apiKey",
}


def _serialise(obj: Any) -> Any:
    """Make dataclass + datetime payloads JSON-roundtrippable."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _serialise(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _serialise(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialise(v) for v in obj]
    return obj


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return a sanitised snapshot of the current integration state."""
    coordinator: AranetCoordinator = entry.runtime_data
    snapshot = coordinator.data

    return async_redact_data(
        {
            "config_entry": {
                "title": entry.title,
                "domain": entry.domain,
                "data": dict(entry.data),
                "options": dict(entry.options),
                "unique_id": entry.unique_id,
                "version": entry.version,
            },
            "coordinator": {
                "name": coordinator.name,
                "update_interval_seconds": (
                    coordinator.update_interval.total_seconds()
                    if coordinator.update_interval
                    else None
                ),
                "last_update_success": coordinator.last_update_success,
            },
            "counts": {
                "sensors": len(snapshot.sensors),
                "bases": len(snapshot.bases),
                "readings": len(snapshot.readings),
                "active_alarms": len(snapshot.alarms),
            },
            "sensors": _serialise(list(snapshot.sensors.values())),
            "bases": _serialise(list(snapshot.bases.values())),
            "readings": [
                {
                    "sensor": k[0],
                    "metric": k[1],
                    **_serialise(dataclasses.asdict(v)),
                }
                for k, v in snapshot.readings.items()
            ],
            "alarms": _serialise(list(snapshot.alarms.values())),
            "integration_domain": DOMAIN,
        },
        REDACT,
    )
