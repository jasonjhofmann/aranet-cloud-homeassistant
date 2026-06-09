"""Binary-sensor tests — low-battery alarm + base connectivity (inverted)."""

from __future__ import annotations

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.aranet_cloud.const import DOMAIN

from . import fixtures_data as data
from .conftest import build_mock_client, setup_integration, state_for

LOW_BATT_AIR = f"{DOMAIN}_{data.AIR_SENSOR_SERIAL}_low_battery"
LOW_BATT_SOIL = f"{DOMAIN}_{data.SOIL_SENSOR_SERIAL}_low_battery"
BASE_OFFLINE = f"{DOMAIN}_base_{data.BASE_ID}_offline"


async def test_counts_one_per_battery_sensor_plus_base(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Two battery-reporting sensors + one base = 3 binary sensors."""
    ent_reg = er.async_get(hass)
    entries = er.async_entries_for_config_entry(ent_reg, init_integration.entry_id)
    binary = [e for e in entries if e.domain == "binary_sensor"]
    assert len(binary) == 3


async def test_low_battery_off_when_no_alarm(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """No active alarm → low-battery binary sensor is off."""
    assert state_for(hass, "binary_sensor", LOW_BATT_AIR).state == STATE_OFF


async def test_low_battery_on_only_for_alarmed_sensor(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """An active low-battery alarm flips only the matching sensor's entity."""
    client = build_mock_client(alarms=[data.build_low_battery_alarm()])
    await setup_integration(hass, mock_config_entry, client)

    assert state_for(hass, "binary_sensor", LOW_BATT_AIR).state == STATE_ON
    assert state_for(hass, "binary_sensor", LOW_BATT_SOIL).state == STATE_OFF


async def test_base_connectivity_on_when_no_alarm(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Connectivity class: on = connected. No offline alarm → on."""
    assert state_for(hass, "binary_sensor", BASE_OFFLINE).state == STATE_ON


async def test_base_connectivity_off_when_offline_alarm(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """An active offline alarm inverts the connectivity sensor to off."""
    client = build_mock_client(alarms=[data.build_base_offline_alarm()])
    await setup_integration(hass, mock_config_entry, client)

    assert state_for(hass, "binary_sensor", BASE_OFFLINE).state == STATE_OFF
