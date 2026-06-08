"""Aranet Cloud integration for Home Assistant — entry point.

Per HA's modern pattern:

* :func:`async_setup_entry` is called once per config entry. It instantiates
  the :class:`AranetCloudClient` (reusing HA's shared aiohttp session),
  spins up the coordinator (polling at a fixed cadence; see
  :data:`~.const.DEFAULT_SCAN_INTERVAL`), awaits the first refresh so platforms
  have data on first tick, pre-registers the base devices so platforms can
  safely set ``via_device`` references, and forwards to all platforms.
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

    # Register base devices up front so sensor entities can reference them via
    # ``via_device`` (HA requires the parent to exist before the child).
    _register_base_devices(hass, entry, coordinator)

    # Keep the device set in sync on every refresh: register bases that appear
    # later (dynamic-devices) and prune devices the cloud no longer reports
    # (stale-devices). Registered before the platforms forward so it runs ahead
    # of the platform add-entity listeners on each coordinator update.
    @callback
    def _sync_devices() -> None:
        _register_base_devices(hass, entry, coordinator)
        _async_remove_stale_devices(hass, entry, coordinator)

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
    hass: HomeAssistant, entry: AranetConfigEntry, coordinator: AranetCoordinator
) -> None:
    """Drop devices for sensors/bases the cloud no longer reports."""
    snapshot = coordinator.data
    current: set[tuple[str, str]] = {
        (DOMAIN, f"base_{base.id}") for base in snapshot.bases.values()
    }
    current |= {(DOMAIN, sensor.serial) for sensor in snapshot.sensors.values()}

    device_reg = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_reg, entry.entry_id):
        if device.identifiers.isdisjoint(current):
            device_reg.async_update_device(
                device.id, remove_config_entry_id=entry.entry_id
            )
