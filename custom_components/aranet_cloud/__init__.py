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

from aranet_cloud import AranetCloudClient
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

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

    # Pre-register the base devices so platforms can safely set ``via_device``
    # references on sensor entities. HA deprecated implicit parent-device
    # creation in DeviceInfo; from 2025.12 onwards the parent must exist by
    # the time the child is registered. Doing it here once (rather than relying
    # on platform-add order) is the canonical pattern.
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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AranetConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
