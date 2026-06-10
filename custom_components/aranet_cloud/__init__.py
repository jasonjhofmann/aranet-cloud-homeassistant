"""Aranet Cloud integration for Home Assistant — entry point.

Per HA's modern pattern:

* :func:`async_setup_entry` is called once per config entry. It instantiates
  the :class:`AranetCloudClient` (reusing HA's shared aiohttp session),
  spins up the coordinator (polling at a fixed cadence; see
  :data:`~.const.DEFAULT_SCAN_INTERVAL`), awaits the first refresh so platforms
  have data on first tick, pre-registers the base devices so platforms can
  safely set ``via_device`` references, and forwards to all platforms.
  A coordinator listener then keeps the device set in sync on every poll —
  registering base devices that appear later (see :func:`_register_base_devices`)
  and pruning devices the account stops reporting
  (see :func:`_async_remove_stale_devices`). Per-platform listeners add the
  matching entities (dynamic devices).
* :func:`async_unload_entry` tears the platforms down. The aiohttp session
  is HA's, so we don't close anything.

Poll interval is not user-configurable (HA Core convention — the integration
owns its cadence). Change :data:`~.const.DEFAULT_SCAN_INTERVAL_SECONDS` if
the upstream sample rate ever changes.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from aranet_cloud import AranetCloudClient

from .const import DOMAIN, MANUFACTURER
from .coordinator import AranetCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

# A device must be absent from this many CONSECUTIVE successful refreshes
# before it is pruned from the registry. One cloud hiccup (or an empty-but-
# successful response) must never wipe the fleet's devices and entity
# registry entries — with the default 60 s poll this means a sensor has to
# be gone for ~3 minutes before HA forgets it.
STALE_DEVICE_THRESHOLD = 3

# Typed alias — coordinator stored on entry.runtime_data per HA's modern pattern.
type AranetConfigEntry = ConfigEntry[AranetCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: AranetConfigEntry) -> bool:
    """Set up Aranet Cloud from a config entry."""
    api_key: str = entry.data[CONF_API_KEY]
    session = async_get_clientsession(hass)
    client = AranetCloudClient(api_key=api_key, session=session)

    coordinator = AranetCoordinator(hass, entry, client=client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    _LOGGER.debug(
        "Set up '%s': %d sensor(s), %d base(s), polling every %s",
        entry.title,
        len(coordinator.data.sensors),
        len(coordinator.data.bases),
        coordinator.update_interval,
    )

    # Register base devices up front so sensor entities can reference them via
    # ``via_device`` (HA requires the parent to exist before the child).
    _register_base_devices(hass, entry, coordinator)

    # Keep the device set in sync on every refresh: register bases that appear
    # later (dynamic-devices) and prune devices the cloud no longer reports
    # (stale-devices). Registered before the platforms forward so it runs ahead
    # of the platform add-entity listeners on each coordinator update.
    # Consecutive-absence counter per device-registry ID, feeding the
    # stale-device hysteresis (see _async_remove_stale_devices).
    absence_counts: dict[str, int] = {}

    @callback
    def _sync_devices() -> None:
        _register_base_devices(hass, entry, coordinator)
        _async_remove_stale_devices(hass, entry, coordinator, absence_counts)

    entry.async_on_unload(coordinator.async_add_listener(_sync_devices))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AranetConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


@callback
def _register_base_devices(
    hass: HomeAssistant, entry: AranetConfigEntry, coordinator: AranetCoordinator
) -> None:
    """Create/update a device for every base station in the snapshot."""
    device_reg = dr.async_get(hass)
    for base in coordinator.data.bases.values():
        device_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"base_{base.id}")},
            name=base.name or f"Aranet base {base.id}",
            manufacturer=MANUFACTURER,
            model=base.product or "Aranet Base",
            sw_version=base.firmware or None,
            serial_number=base.id,
        )


@callback
def _async_remove_stale_devices(
    hass: HomeAssistant,
    entry: AranetConfigEntry,
    coordinator: AranetCoordinator,
    absence_counts: dict[str, int],
) -> None:
    """Drop devices for sensors/bases the cloud no longer reports.

    Guarded two ways so a transient cloud problem can never wipe the fleet:

    * An *empty* snapshot (no sensors AND no bases) is treated as suspect —
      the API returns a successful empty body on some hiccups — and never
      prunes anything.
    * A device must be absent for :data:`STALE_DEVICE_THRESHOLD` consecutive
      successful refreshes before it is removed. Reappearing resets its
      counter.
    """
    snapshot = coordinator.data
    if not snapshot.sensors and not snapshot.bases:
        _LOGGER.debug(
            "Snapshot is empty — skipping stale-device pruning (a cloud "
            "hiccup can present as a successful empty fleet)"
        )
        return

    current: set[tuple[str, str]] = {
        (DOMAIN, f"base_{base.id}") for base in snapshot.bases.values()
    }
    current |= {(DOMAIN, sensor.serial) for sensor in snapshot.sensors.values()}

    device_reg = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_reg, entry.entry_id):
        if not device.identifiers.isdisjoint(current):
            absence_counts.pop(device.id, None)
            continue
        misses = absence_counts.get(device.id, 0) + 1
        absence_counts[device.id] = misses
        if misses < STALE_DEVICE_THRESHOLD:
            _LOGGER.debug(
                "Device '%s' absent from refresh %d/%d — deferring removal",
                device.name_by_user or device.name or device.id,
                misses,
                STALE_DEVICE_THRESHOLD,
            )
            continue
        absence_counts.pop(device.id, None)
        _LOGGER.info(
            "Removing device '%s' — it has not been reported by the "
            "Aranet Cloud account for %d consecutive refreshes",
            device.name_by_user or device.name or device.id,
            STALE_DEVICE_THRESHOLD,
        )
        device_reg.async_update_device(device.id, remove_config_entry_id=entry.entry_id)
