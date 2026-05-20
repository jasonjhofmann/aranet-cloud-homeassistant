"""Aranet Cloud integration for Home Assistant.

Top-level entrypoint:

* :func:`async_setup_entry` — instantiated once per config entry. Creates
  the shared ``AranetCloudClient`` (reusing HA's aiohttp session), spins up
  the coordinator, does the first refresh (so entities have data on first
  state-machine tick), and forwards to the sensor platform.
* :func:`async_unload_entry` — tears down platforms + closes nothing (we
  injected HA's session, so it's not ours to close).

A typed alias ``AranetConfigEntry`` carries the runtime data, so platforms
can pull the coordinator out without a string key in ``hass.data``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aranet_cloud import AranetCloudClient
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_SCAN_INTERVAL
from .coordinator import AranetCoordinator

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

# Typed alias — coordinator stored on entry.runtime_data per HA's modern pattern.
type AranetConfigEntry = ConfigEntry[AranetCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: AranetConfigEntry) -> bool:
    """Set up Aranet Cloud from a config entry."""
    api_key: str = entry.data[CONF_API_KEY]
    session = async_get_clientsession(hass)
    client = AranetCloudClient(api_key=api_key, session=session)

    coordinator = AranetCoordinator(
        hass,
        client=client,
        scan_interval=DEFAULT_SCAN_INTERVAL,
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AranetConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
