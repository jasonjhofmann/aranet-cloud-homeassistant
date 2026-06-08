"""Setup / unload and coordinator error-path tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from aranet_cloud import AranetAuthError, AranetError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.aranet_cloud.const import DOMAIN

from . import fixtures_data as data
from .conftest import build_mock_client, setup_integration

SOIL_VWC_UID = f"{DOMAIN}_{data.SOIL_SENSOR_SERIAL}_{data.M_SOIL_VWC}"
SOIL_DEVICE = {(DOMAIN, data.SOIL_SENSOR_SERIAL)}


async def test_setup_and_unload(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A healthy setup loads, registers runtime data, then unloads cleanly."""
    entry = init_integration
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_base_device_pre_registered(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The base station is registered as a device so via_device links resolve."""
    device_reg = dr.async_get(hass)
    base_device = device_reg.async_get_device(
        identifiers={(DOMAIN, f"base_{data.BASE_ID}")}
    )
    assert base_device is not None
    assert base_device.manufacturer == "Aranet"
    assert base_device.serial_number == data.BASE_ID


async def test_setup_auth_failure_triggers_reauth(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A 401 on first refresh fails setup and starts the reauth flow."""
    client = build_mock_client()
    client.get_sensors.side_effect = AranetAuthError("invalid key")

    await setup_integration(hass, mock_config_entry, client)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    reauth_flows = [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"].get("source") == "reauth"
    ]
    assert len(reauth_flows) == 1


async def test_setup_api_error_is_retried(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A generic API error on first refresh leaves the entry in retry state."""
    client = build_mock_client()
    client.get_measurements_last.side_effect = AranetError("503 upstream")

    await setup_integration(hass, mock_config_entry, client)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_dynamic_devices_adds_appearing_sensor(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A sensor that shows up after setup gets entities on the next refresh."""
    # Start with only the air sensor present.
    air_only_meas = [
        r for r in data.build_measurement_readings() if r.sensor == data.AIR_SENSOR_ID
    ]
    air_only_tele = [
        r for r in data.build_telemetry_readings() if r.sensor == data.AIR_SENSOR_ID
    ]
    client = build_mock_client(
        sensors=[data.build_air_sensor()],
        measurements=air_only_meas,
        telemetry=air_only_tele,
    )
    await setup_integration(hass, mock_config_entry, client)

    ent_reg = er.async_get(hass)
    assert ent_reg.async_get_entity_id("sensor", DOMAIN, SOIL_VWC_UID) is None

    # Soil sensor now appears in the cloud.
    client.get_sensors.return_value = data.build_sensors()
    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert ent_reg.async_get_entity_id("sensor", DOMAIN, SOIL_VWC_UID) is not None


async def test_stale_devices_are_pruned(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """A sensor the cloud stops reporting has its device removed."""
    device_reg = dr.async_get(hass)
    assert device_reg.async_get_device(identifiers=SOIL_DEVICE) is not None

    # Cloud drops the soil sensor.
    mock_client.get_sensors.return_value = [data.build_air_sensor()]
    await init_integration.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert device_reg.async_get_device(identifiers=SOIL_DEVICE) is None
