"""Coordinator tests — snapshot construction + exception translation keys."""

from __future__ import annotations

import dataclasses

import pytest
from aranet_cloud import AranetAuthError, AranetError, Reading
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.aranet_cloud.const import DOMAIN
from custom_components.aranet_cloud.coordinator import AranetCoordinator

from . import fixtures_data as data
from .conftest import build_mock_client


async def test_update_builds_unified_snapshot(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """The success path indexes the catalog and merges both reading planes.

    Directly exercises ``_async_update_data`` — the platform tests only reach
    this construction incidentally, so the snapshot contract (id indexing, the
    serial→id map, and the measurements⊕telemetry union) is pinned here.
    """
    mock_config_entry.add_to_hass(hass)
    coordinator = AranetCoordinator(hass, mock_config_entry, client=build_mock_client())

    snapshot = await coordinator._async_update_data()

    # Catalog indexed by cloud-numeric id.
    assert set(snapshot.sensors) == {data.AIR_SENSOR_ID, data.SOIL_SENSOR_ID}
    assert data.BASE_ID in snapshot.bases
    # Serial → current numeric id, so serial-keyed entities resolve readings
    # even after a cloud-side rekey.
    assert snapshot.id_by_serial[data.AIR_SENSOR_SERIAL] == data.AIR_SENSOR_ID
    # readings is the UNION of the measurements/last (gauge: CO2) and
    # telemetry/last (battery) planes — both resolve from the one dict.
    assert snapshot.reading(data.AIR_SENSOR_ID, data.M_CO2).value == pytest.approx(
        612.0
    )
    assert snapshot.reading(data.AIR_SENSOR_ID, data.M_BATTERY).value == pytest.approx(
        94.0
    )
    # The serial-keyed lookup mirrors the id-keyed one.
    assert snapshot.reading_for_serial(
        data.AIR_SENSOR_SERIAL, data.M_CO2
    ).value == pytest.approx(612.0)


async def test_telemetry_wins_on_metric_key_collision(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """When both planes report the same (sensor, metric), telemetry is last-writer.

    ``readings`` is built from ``(*measurements, *telemetry)`` so a key present
    on both planes resolves to the telemetry value. Pin that ordering as a
    deliberate contract rather than an accident of construction.
    """
    collision_meas = [
        Reading(
            sensor=data.AIR_SENSOR_ID,
            metric=data.M_BATTERY,
            unit="115",
            value=50.0,
            time=data.FIXED_TIME,
        )
    ]
    collision_tele = [
        Reading(
            sensor=data.AIR_SENSOR_ID,
            metric=data.M_BATTERY,
            unit="115",
            value=88.0,
            time=data.FIXED_TIME,
        )
    ]
    client = build_mock_client(measurements=collision_meas, telemetry=collision_tele)
    mock_config_entry.add_to_hass(hass)
    coordinator = AranetCoordinator(hass, mock_config_entry, client=client)

    snapshot = await coordinator._async_update_data()

    assert snapshot.reading(data.AIR_SENSOR_ID, data.M_BATTERY).value == pytest.approx(
        88.0
    )


async def test_active_alarm_picks_highest_severity(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Two rules on one (sensor, metric): the highest-severity alarm wins."""
    low = data.build_low_battery_alarm()  # severity 2
    high = dataclasses.replace(low, id="alarm-batt-2", severity=5)
    client = build_mock_client(alarms=[low, high])
    mock_config_entry.add_to_hass(hass)
    coordinator = AranetCoordinator(hass, mock_config_entry, client=client)

    snapshot = await coordinator._async_update_data()

    winner = snapshot.active_alarm(data.AIR_SENSOR_ID, data.M_BATTERY)
    assert winner is not None
    assert winner.severity == 5
    assert winner.id == "alarm-batt-2"
    # The serial-keyed variant resolves the same winner.
    serial_winner = snapshot.active_alarm_for_serial(
        data.AIR_SENSOR_SERIAL, data.M_BATTERY
    )
    assert serial_winner is not None
    assert serial_winner.id == "alarm-batt-2"


async def test_update_handles_empty_fleet(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """An empty-but-successful response builds an empty snapshot without error."""
    client = build_mock_client(
        sensors=[], bases=[], measurements=[], telemetry=[], alarms=[]
    )
    mock_config_entry.add_to_hass(hass)
    coordinator = AranetCoordinator(hass, mock_config_entry, client=client)

    snapshot = await coordinator._async_update_data()

    assert snapshot.sensors == {}
    assert snapshot.bases == {}
    assert snapshot.readings == {}
    assert snapshot.alarms == {}
    assert snapshot.id_by_serial == {}


async def test_auth_error_is_translated(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A 401 raises ConfigEntryAuthFailed with a translation key, not a raw message."""
    mock_config_entry.add_to_hass(hass)
    client = build_mock_client()
    client.get_sensors.side_effect = AranetAuthError("nope")
    coordinator = AranetCoordinator(hass, mock_config_entry, client=client)

    with pytest.raises(ConfigEntryAuthFailed) as exc:
        await coordinator._async_update_data()

    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "auth_failed"


async def test_update_error_is_translated(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Other API errors raise UpdateFailed with a translation key + the detail."""
    mock_config_entry.add_to_hass(hass)
    client = build_mock_client()
    client.get_measurements_last.side_effect = AranetError("503 upstream")
    coordinator = AranetCoordinator(hass, mock_config_entry, client=client)

    with pytest.raises(UpdateFailed) as exc:
        await coordinator._async_update_data()

    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "update_failed"
    assert exc.value.translation_placeholders == {"error": "503 upstream"}
