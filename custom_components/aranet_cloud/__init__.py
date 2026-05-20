"""Aranet Cloud integration for Home Assistant — entry point.

Per HA's modern pattern:

* :func:`async_setup_entry` is called once per config entry. It instantiates
  the :class:`AranetCloudClient` (reusing HA's shared aiohttp session),
  reads the scan-interval option (defaulting to 60 s), spins up the
  coordinator, awaits the first refresh so platforms have data on first
  tick, and forwards to all platforms.
* :func:`async_unload_entry` tears the platforms down. The aiohttp session
  is HA's, so we don't close anything.
* :func:`_async_options_updated` reloads the entry when the user changes
  options (e.g. scan interval) so the new value takes effect immediately.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from aranet_cloud import AranetCloudClient
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
    MANUFACTURER,
)
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

    scan_seconds: int = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS)
    coordinator = AranetCoordinator(
        hass,
        client=client,
        scan_interval=timedelta(seconds=scan_seconds),
    )
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

    # React to options changes (e.g. user changes the poll interval) by
    # reloading the entry — simplest correct behaviour; HA's reload is fast.
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AranetConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(hass: HomeAssistant, entry: AranetConfigEntry) -> None:
    """Reload the entry when the user changes options."""
    _LOGGER.debug("Options updated for %s; reloading entry", entry.title)
    await hass.config_entries.async_reload(entry.entry_id)
