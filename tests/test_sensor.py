"""Sensor platform tests — values, units, availability, diagnostics entity."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest
from aranet_cloud import AranetError
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.aranet_cloud.const import DOMAIN

from . import fixtures_data as data
from .conftest import build_mock_client, setup_integration, state_for

AIR = data.AIR_SENSOR_SERIAL


def _uid(serial: str, metric: str) -> str:
    return f"{DOMAIN}_{serial}_{metric}"


async def test_measurement_values_and_units(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Gauge + telemetry readings surface with mapped units."""
    cases = [
        (_uid(AIR, data.M_TEMPERATURE), 22.7, "°C"),
        (_uid(AIR, data.M_HUMIDITY), 41.0, "%"),
        (_uid(AIR, data.M_CO2), 612.0, "ppm"),
        (_uid(AIR, data.M_BATTERY), 94.0, "%"),
    ]
    for unique_id, value, unit in cases:
        state = state_for(hass, "sensor", unique_id)
        assert state is not None
        assert float(state.state) == pytest.approx(value)
        assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == unit


async def test_entity_counts(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Two 6-metric sensors + one base firmware diagnostic = 13 sensor entities."""
    ent_reg = er.async_get(hass)
    entries = er.async_entries_for_config_entry(ent_reg, init_integration.entry_id)
    sensor_entities = [e for e in entries if e.domain == "sensor"]
    assert len(sensor_entities) == 13


async def test_rssi_disabled_by_default(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Signal strength is registered but disabled by default (no state)."""
    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, _uid(AIR, data.M_RSSI))
    assert entity_id is not None
    registry_entry = ent_reg.async_get(entity_id)
    assert registry_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(entity_id) is None


async def test_base_firmware_is_diagnostic(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The base firmware sensor reports the version and is a diagnostic entity."""
    unique_id = f"{DOMAIN}_base_{data.BASE_ID}_firmware"
    state = state_for(hass, "sensor", unique_id)
    assert state is not None
    assert state.state == "1.0.0"

    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id is not None
    assert ent_reg.async_get(entity_id).entity_category is EntityCategory.DIAGNOSTIC


async def test_missing_reading_marks_unavailable(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A skill with no matching reading yields an unavailable entity."""
    # Drop the CO2 reading but keep the skill (entity is created, value is None).
    measurements = [
        r for r in data.build_measurement_readings() if r.metric != data.M_CO2
    ]
    client = build_mock_client(measurements=measurements)
    await setup_integration(hass, mock_config_entry, client)

    state = state_for(hass, "sensor", _uid(AIR, data.M_CO2))
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_entities_unavailable_after_failed_refresh(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """When a later coordinator refresh fails, entities go unavailable."""
    coordinator = init_integration.runtime_data
    mock_client.get_measurements_last.side_effect = AranetError("transient")

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert not coordinator.last_update_success
    state = state_for(hass, "sensor", _uid(AIR, data.M_TEMPERATURE))
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_specialty_metrics_render(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """The added catalog metrics render with the right unit and device class."""
    client = build_mock_client(
        sensors=[data.build_specialty_sensor()],
        measurements=data.build_specialty_readings(),
        telemetry=[],
    )
    await setup_integration(hass, mock_config_entry, client)
    ser = data.SPECIALTY_SENSOR_SERIAL

    # metric, value, expected unit, expected device_class (None = no class)
    cases = [
        (data.M_VOLTAGE, 3.3, "V", "voltage"),
        (data.M_WEIGHT, 12.5, "kg", "weight"),
        (data.M_DISTANCE, 1.42, "m", None),  # "mil" option → no device class
        (data.M_DIFF_PRESSURE, 25.0, "Pa", None),  # "mmH₂O" option → no class
        (data.M_RADON, 48.0, "Bq/m³", None),  # HA has no radon class
        (data.M_FRACTION, 0.5, None, None),  # dimensionless
    ]
    for metric, value, unit, dev_class in cases:
        state = state_for(hass, "sensor", _uid(ser, metric))
        assert state is not None, f"no entity for metric {metric}"
        assert float(state.state) == pytest.approx(value)
        assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == unit
        assert state.attributes.get(ATTR_DEVICE_CLASS) == dev_class


async def test_unknown_metric_is_skipped(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A metric we don't model produces no entity, and is logged once at debug."""
    from aranet_cloud import Sensor, Skill

    odd = Sensor(
        id="999001",
        serial="0ZZ99",
        name="Mystery",
        type="X9V9",
        skills=[
            Skill(metric="9999", active=True),
            Skill(metric=data.M_CO2, active=True),
        ],
    )
    client = build_mock_client(
        sensors=[odd],
        measurements=[
            data.Reading(
                sensor="999001",
                metric=data.M_CO2,
                unit="3",
                value=500.0,
                time=data.FIXED_TIME,
            )
        ],
        telemetry=[],
    )
    with caplog.at_level(logging.DEBUG, logger="custom_components.aranet_cloud"):
        await setup_integration(hass, mock_config_entry, client)

    ent_reg = er.async_get(hass)
    # The modelled CO2 metric exists...
    assert ent_reg.async_get_entity_id("sensor", DOMAIN, _uid("0ZZ99", data.M_CO2))
    # ...but the unknown metric was skipped — and that skip is logged.
    assert ent_reg.async_get_entity_id("sensor", DOMAIN, _uid("0ZZ99", "9999")) is None
    assert "metric id 9999" in caplog.text
