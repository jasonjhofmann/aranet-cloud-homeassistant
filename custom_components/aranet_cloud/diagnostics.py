"""Diagnostics platform — sanitised "Download diagnostics" snapshot.

Produces a JSON dump suitable for pasting into a GitHub issue. Includes:

* Config-entry + coordinator status: entry state, poll interval, last-update
  success, and the last exception (so a failing poll's cause is in the dump,
  not only the log)
* Counts: sensors / bases / readings / active alarms
* Sensor + base catalog (full metadata)
* Latest reading per (sensor × metric)
* Active alarms
* ``generated_at`` — a wall-clock reference so the readings' own timestamps are
  interpretable (a stale-but-successful poll is otherwise indistinguishable
  from a healthy fleet in a pasted dump)

Works even before the first refresh completes: an entry stuck in
``SETUP_RETRY`` / reauth has no coordinator yet, but that is exactly when a
user is told to download diagnostics — so a redacted *partial* dump is returned
instead of raising.

Redacts: the API key and the hashed unique_id (which is derived from the
key). Everything else is non-sensitive metadata about the user's setup.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.redact import REDACTED
from homeassistant.util import dt as dt_util

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import AranetCoordinator

# Keys redacted at any depth. Beyond the keys the dump contains today, this
# pre-lists sensitive keys from Aranet Cloud's RAW API payloads (inventoried
# from the aranet-cloud client's parsers) that we never include today but
# would need scrubbing if a future revision attached a raw payload or
# request context to the dump. Unused keys cost nothing.
REDACT = {
    # Present in today's dump
    CONF_API_KEY,
    "unique_id",
    "config",  # Base.config — enterprise gateway configuration blob
    "region",  # Base.region — account region
    "note",  # Alarm.note — user free-text can contain anything
    # Raw-payload keys (hypothetical future inclusion)
    "location",  # free-text sensor placement
    "notes",  # user free-text
    # Request context (hypothetical future inclusion). The live auth header is
    # spelled "ApiKey" (see README curl example); include the real casing plus
    # common variants — async_redact_data matches keys case-sensitively.
    "Authorization",
    "ApiKey",
    "apiKey",
}


def _format_exc(exc: BaseException) -> str:
    """``ExcType: message`` — or just ``ExcType`` when the message is empty.

    Uses an explicit empty-message check rather than ``rstrip(": ")`` (which is
    a character-set strip that would silently truncate a legitimate message
    ending in ``:`` or whitespace).
    """
    message = str(exc)
    name = type(exc).__name__
    return f"{name}: {message}" if message else name


def _describe_exception(
    exc: BaseException | None, secret: str | None = None
) -> str | None:
    """Human-readable summary of the coordinator's last failure, with its cause.

    The coordinator raises *translated* ``UpdateFailed`` / ``ConfigEntryAuthFailed``
    whose ``str()`` is empty — the real API/network reason is the chained
    ``__cause__`` (raised ``from err``). Surface both so a failing poll's cause
    lands in the dump, not only the log.

    ``async_redact_data`` only matches sensitive *dict keys*; it cannot reach a
    secret embedded in this free-text string. So the rendered summary is
    additionally scrubbed of the config entry's API-key value: a future library
    revision that echoed the key into an error message (URL query param, header
    echo, auth-response body) cannot leak it into a shared dump.
    """
    if exc is None:
        return None
    summary = _format_exc(exc)
    cause = exc.__cause__
    if cause is not None:
        summary += f" (caused by {_format_exc(cause)})"
    if secret:
        summary = summary.replace(secret, REDACTED)
    return summary


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
    """Return a sanitised snapshot of the current integration state.

    Tolerates a not-yet-loaded entry (setup still failing): ``runtime_data`` is
    assigned only after the first refresh succeeds, so an entry in
    ``SETUP_RETRY`` / reauth has no coordinator (or a coordinator with no
    snapshot). In that case a redacted *partial* dump is returned — the failure
    is still describable, exactly when the dump is most useful.
    """
    secret: str | None = entry.data.get(CONF_API_KEY)
    config_entry = {
        "title": entry.title,
        "domain": entry.domain,
        "data": dict(entry.data),
        "options": dict(entry.options),
        "unique_id": entry.unique_id,
        "version": entry.version,
        "state": entry.state.value,
    }

    coordinator: AranetCoordinator | None = getattr(entry, "runtime_data", None)
    snapshot = coordinator.data if coordinator is not None else None

    if coordinator is None or snapshot is None:
        # Setup has not completed a successful first refresh — no snapshot to
        # dump. Return what we can so the failure is still describable.
        return async_redact_data(
            {
                "config_entry": config_entry,
                "coordinator": (
                    None
                    if coordinator is None
                    else {
                        "name": coordinator.name,
                        "last_update_success": coordinator.last_update_success,
                        "last_exception": _describe_exception(
                            coordinator.last_exception, secret
                        ),
                    }
                ),
                "note": (
                    "Coordinator not initialised — setup has not completed a "
                    "successful first refresh, so no snapshot is available."
                ),
                "generated_at": dt_util.utcnow().isoformat(),
                "integration_domain": DOMAIN,
            },
            REDACT,
        )

    return async_redact_data(
        {
            "config_entry": config_entry,
            "coordinator": {
                "name": coordinator.name,
                "update_interval_seconds": (
                    coordinator.update_interval.total_seconds()
                    if coordinator.update_interval
                    else None
                ),
                "last_update_success": coordinator.last_update_success,
                # Only surface the exception while it is *current*. HA's
                # coordinator retains ``last_exception`` after a recovery (it is
                # cleared only at construction), so on a succeeded poll it would
                # otherwise present an already-resolved failure as if live.
                "last_exception": (
                    None
                    if coordinator.last_update_success
                    else _describe_exception(coordinator.last_exception, secret)
                ),
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
            "generated_at": dt_util.utcnow().isoformat(),
            "integration_domain": DOMAIN,
        },
        REDACT,
    )
