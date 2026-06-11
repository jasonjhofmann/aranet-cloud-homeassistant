"""Binary-sensor tests — low-battery alarm + base connectivity (inverted)."""

from __future__ import annotations

import dataclasses
from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
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


async def test_alarm_with_null_value_still_drives_entity(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """An alarm whose value/worst are null (aranet-cloud 0.2.0) still registers.

    The alarm logic only checks alarm *presence* (never ``.value`` /
    ``.worst``), so null numeric fields must not crash or change behavior.
    """
    alarm = dataclasses.replace(data.build_low_battery_alarm(), value=None, worst=None)
    client = build_mock_client(alarms=[alarm])
    await setup_integration(hass, mock_config_entry, client)

    assert state_for(hass, "binary_sensor", LOW_BATT_AIR).state == STATE_ON


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


# ---------------------------------------------------------------------------
# Staleness — low-battery follows its reading's age; base-offline must NOT
# ---------------------------------------------------------------------------


async def test_low_battery_unavailable_when_battery_reading_stale(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A stale battery reading marks only that sensor's low-battery entity."""
    from custom_components.aranet_cloud.sensor import READING_MAX_AGE

    stale_time = data.FIXED_TIME - READING_MAX_AGE - timedelta(minutes=1)
    telemetry = [
        dataclasses.replace(r, time=stale_time)
        if r.metric == data.M_BATTERY and r.sensor == data.AIR_SENSOR_ID
        else r
        for r in data.build_telemetry_readings()
    ]
    client = build_mock_client(telemetry=telemetry)
    await setup_integration(hass, mock_config_entry, client)

    assert state_for(hass, "binary_sensor", LOW_BATT_AIR).state == STATE_UNAVAILABLE
    # The sibling with fresh telemetry is unaffected.
    assert state_for(hass, "binary_sensor", LOW_BATT_SOIL).state == STATE_OFF


async def test_low_battery_without_reading_stays_available(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """No battery reading at all → benefit of the doubt (alarm feed is live)."""
    telemetry = [
        r
        for r in data.build_telemetry_readings()
        if not (r.metric == data.M_BATTERY and r.sensor == data.AIR_SENSOR_ID)
    ]
    client = build_mock_client(telemetry=telemetry)
    await setup_integration(hass, mock_config_entry, client)

    assert state_for(hass, "binary_sensor", LOW_BATT_AIR).state == STATE_OFF


async def test_base_offline_not_gated_on_stale_last_seen(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A dark base must keep REPORTING Disconnected, not go unavailable.

    A stale ``Base.last_seen`` is precisely the condition this connectivity
    entity exists to surface — gating availability on it would mask the very
    outage it reports.
    """
    from custom_components.aranet_cloud.sensor import READING_MAX_AGE

    base = data.build_base()
    base.last_seen = data.FIXED_TIME - READING_MAX_AGE - timedelta(hours=2)
    client = build_mock_client(bases=[base], alarms=[data.build_base_offline_alarm()])
    await setup_integration(hass, mock_config_entry, client)

    # off = disconnected (connectivity class, inverted) — NOT unavailable.
    assert state_for(hass, "binary_sensor", BASE_OFFLINE).state == STATE_OFF


# ---------------------------------------------------------------------------
# Skill deactivation/re-activation — bookkeeping must not re-add unique_ids
# ---------------------------------------------------------------------------


async def test_battery_skill_reactivation_does_not_duplicate_entity(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Battery skill flips inactive then back → no duplicate low-battery add."""
    from aranet_cloud import Skill

    coordinator = init_integration.runtime_data

    air = data.build_air_sensor()
    air.skills = [
        Skill(metric=s.metric, active=False) if s.metric == data.M_BATTERY else s
        for s in air.skills
    ]
    mock_client.get_sensors.return_value = [air, data.build_soil_sensor()]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    mock_client.get_sensors.return_value = data.build_sensors()
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert "already exists" not in caplog.text
    ent_reg = er.async_get(hass)
    entries = er.async_entries_for_config_entry(ent_reg, init_integration.entry_id)
    assert [e.unique_id for e in entries].count(LOW_BATT_AIR) == 1
    assert state_for(hass, "binary_sensor", LOW_BATT_AIR).state == STATE_OFF
