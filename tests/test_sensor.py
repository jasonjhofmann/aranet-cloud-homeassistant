"""Sensor platform tests — values, units, availability, diagnostics entity."""

from __future__ import annotations

import dataclasses
import logging
from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from aranet_cloud import AranetError, Links
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
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


async def test_null_reading_value_is_unknown_not_zero(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A reading with a null value (aranet-cloud 0.2.0) → state unknown.

    The cloud can report ``null`` for a metric; since aranet-cloud 0.2.0
    ``Reading.value`` is ``float | None`` instead of coercing to ``0.0``.
    The entity stays *available* (the reading itself is fresh) but its
    state must be *unknown* — never a fabricated zero.
    """
    measurements = [
        dataclasses.replace(r, value=None)
        if r.metric == data.M_CO2 and r.sensor == data.AIR_SENSOR_ID
        else r
        for r in data.build_measurement_readings()
    ]
    client = build_mock_client(measurements=measurements)
    await setup_integration(hass, mock_config_entry, client)

    state = state_for(hass, "sensor", _uid(AIR, data.M_CO2))
    assert state is not None
    assert state.state == STATE_UNKNOWN
    # Fresh siblings with real values are unaffected.
    temp = state_for(hass, "sensor", _uid(AIR, data.M_TEMPERATURE))
    assert float(temp.state) == pytest.approx(22.7)


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


# ---------------------------------------------------------------------------
# Staleness — a dead sensor must not report its last value as live forever
# ---------------------------------------------------------------------------


async def test_stale_reading_marks_unavailable(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A reading older than READING_MAX_AGE makes only that entity unavailable."""
    from custom_components.aranet_cloud.sensor import READING_MAX_AGE

    stale_time = data.FIXED_TIME - READING_MAX_AGE - timedelta(minutes=1)
    measurements = [
        dataclasses.replace(r, time=stale_time)
        if r.metric == data.M_CO2 and r.sensor == data.AIR_SENSOR_ID
        else r
        for r in data.build_measurement_readings()
    ]
    client = build_mock_client(measurements=measurements)
    await setup_integration(hass, mock_config_entry, client)

    assert state_for(hass, "sensor", _uid(AIR, data.M_CO2)).state == STATE_UNAVAILABLE
    # Fresh siblings stay available.
    assert (
        state_for(hass, "sensor", _uid(AIR, data.M_TEMPERATURE)).state
        != STATE_UNAVAILABLE
    )


async def test_fresh_reading_is_available(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Readings at FIXED_TIME (== frozen now) are well inside the threshold."""
    state = state_for(hass, "sensor", _uid(AIR, data.M_CO2))
    assert state.state != STATE_UNAVAILABLE


async def test_reading_without_timestamp_stays_available(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """No timestamp → benefit of the doubt (can't judge staleness)."""
    measurements = [
        dataclasses.replace(r, time=None)
        if r.metric == data.M_CO2 and r.sensor == data.AIR_SENSOR_ID
        else r
        for r in data.build_measurement_readings()
    ]
    client = build_mock_client(measurements=measurements)
    await setup_integration(hass, mock_config_entry, client)

    assert state_for(hass, "sensor", _uid(AIR, data.M_CO2)).state != STATE_UNAVAILABLE


# ---------------------------------------------------------------------------
# Cloud-numeric ID churn — entities are keyed by serial and must survive it
# ---------------------------------------------------------------------------


async def test_cloud_id_change_with_stable_serial_keeps_reporting(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Delete-and-re-add in the cloud (new numeric id, same serial) keeps data flowing."""
    new_id = "7777777"
    air = data.build_air_sensor()
    air.id = new_id  # same serial, rekeyed cloud id
    mock_client.get_sensors.return_value = [air, data.build_soil_sensor()]
    mock_client.get_measurements_last.return_value = (
        [
            dataclasses.replace(r, sensor=new_id, value=700.0)
            if r.sensor == data.AIR_SENSOR_ID and r.metric == data.M_CO2
            else (
                dataclasses.replace(r, sensor=new_id)
                if r.sensor == data.AIR_SENSOR_ID
                else r
            )
            for r in data.build_measurement_readings()
        ],
        Links(),
    )

    await init_integration.runtime_data.async_refresh()
    await hass.async_block_till_done()

    state = state_for(hass, "sensor", _uid(AIR, data.M_CO2))
    assert state.state != STATE_UNAVAILABLE
    assert float(state.state) == pytest.approx(700.0)


# ---------------------------------------------------------------------------
# Device-class ↔ unit validation
# ---------------------------------------------------------------------------


def test_every_unit_yields_valid_device_class_combo() -> None:
    """Exhaustive: registry × every unit id must never emit an invalid combo."""
    from homeassistant.components.sensor.const import DEVICE_CLASS_UNITS

    from custom_components.aranet_cloud.const import UNIT_BY_ID, unit_for_id
    from custom_components.aranet_cloud.sensor import (
        METRIC_REGISTRY,
        _effective_device_class,
    )

    for description in METRIC_REGISTRY.values():
        for unit_id in UNIT_BY_ID:
            unit = unit_for_id(unit_id) or None
            device_class = _effective_device_class(description.device_class, unit)
            if device_class is None:
                continue
            allowed = DEVICE_CLASS_UNITS.get(device_class)
            if allowed is None:
                continue  # HA imposes no unit restriction on this class
            assert unit in allowed, (
                f"metric {description.key!r} with unit id {unit_id} ({unit!r}) "
                f"would emit invalid device_class {device_class}"
            )


def test_effective_device_class_known_combos() -> None:
    """Spot-check the audit's specific invalid combos and the V→VOLTAGE promotion."""
    from homeassistant.components.sensor import SensorDeviceClass

    from custom_components.aranet_cloud.sensor import _effective_device_class

    # promotions: a better class beats dropping the class
    assert (
        _effective_device_class(SensorDeviceClass.BATTERY, "V")
        is SensorDeviceClass.VOLTAGE
    )
    assert (
        _effective_device_class(SensorDeviceClass.BATTERY, "mV")
        is SensorDeviceClass.VOLTAGE
    )
    # invalid combos degrade to no class
    assert _effective_device_class(SensorDeviceClass.HUMIDITY, "%RH") is None
    assert (
        _effective_device_class(SensorDeviceClass.ATMOSPHERIC_PRESSURE, "atm") is None
    )
    assert _effective_device_class(SensorDeviceClass.SIGNAL_STRENGTH, "dBW") is None
    assert _effective_device_class(SensorDeviceClass.MOISTURE, "/") is None
    assert _effective_device_class(SensorDeviceClass.CO2, "/") is None
    # valid combos pass through untouched
    assert (
        _effective_device_class(SensorDeviceClass.CO2, "ppm") is SensorDeviceClass.CO2
    )
    assert (
        _effective_device_class(SensorDeviceClass.TEMPERATURE, "°F")
        is SensorDeviceClass.TEMPERATURE
    )


async def test_unknown_unit_renders_value_without_unit(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A reading whose unit id isn't in UNIT_BY_ID shows the value but no unit.

    README contract: "an unrecognised unit shows the value with no unit
    label." The device class is also dropped — CO2 can't be vouched for
    without a ppm-class unit (_effective_device_class).
    """
    measurements = [
        dataclasses.replace(r, unit="9999")
        if r.metric == data.M_CO2 and r.sensor == data.AIR_SENSOR_ID
        else r
        for r in data.build_measurement_readings()
    ]
    client = build_mock_client(measurements=measurements)
    await setup_integration(hass, mock_config_entry, client)

    state = state_for(hass, "sensor", _uid(AIR, data.M_CO2))
    assert float(state.state) == pytest.approx(612.0)
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes
    assert ATTR_DEVICE_CLASS not in state.attributes


async def test_battery_voltage_unit_promotes_to_voltage_class(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Battery telemetry delivered in volts renders as a VOLTAGE sensor, not BATTERY %."""
    telemetry = [
        dataclasses.replace(r, unit="16", value=2.95)
        if r.metric == data.M_BATTERY and r.sensor == data.AIR_SENSOR_ID
        else r
        for r in data.build_telemetry_readings()
    ]
    client = build_mock_client(telemetry=telemetry)
    await setup_integration(hass, mock_config_entry, client)

    state = state_for(hass, "sensor", _uid(AIR, data.M_BATTERY))
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "V"
    assert state.attributes[ATTR_DEVICE_CLASS] == "voltage"


async def test_battery_in_volts_raises_display_precision(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Battery delivered in volts gets ≥2-decimal display precision.

    The BATTERY description pins precision 0 (right for %); a volts reading at
    precision 0 would round 2.95 → '3 V'. _MIN_PRECISION_BY_UNIT floors it.
    """
    telemetry = [
        dataclasses.replace(r, unit="16", value=2.95)
        if r.metric == data.M_BATTERY and r.sensor == data.AIR_SENSOR_ID
        else r
        for r in data.build_telemetry_readings()
    ]
    client = build_mock_client(telemetry=telemetry)
    await setup_integration(hass, mock_config_entry, client)

    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, _uid(AIR, data.M_BATTERY))
    options = ent_reg.async_get(entity_id).options.get("sensor", {})
    assert options.get("suggested_display_precision") == 2


# ---------------------------------------------------------------------------
# Base staleness — Base.last_seen gates the base-bound firmware sensor
# ---------------------------------------------------------------------------


async def test_base_firmware_unavailable_when_last_seen_stale(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A base whose last check-in exceeds READING_MAX_AGE goes unavailable."""
    from custom_components.aranet_cloud.sensor import READING_MAX_AGE

    base = data.build_base()
    base.last_seen = data.FIXED_TIME - READING_MAX_AGE - timedelta(minutes=1)
    client = build_mock_client(bases=[base])
    await setup_integration(hass, mock_config_entry, client)

    unique_id = f"{DOMAIN}_base_{data.BASE_ID}_firmware"
    assert state_for(hass, "sensor", unique_id).state == STATE_UNAVAILABLE


async def test_base_firmware_without_last_seen_stays_available(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """No last_seen timestamp → benefit of the doubt (can't judge staleness)."""
    base = data.build_base()
    base.last_seen = None
    client = build_mock_client(bases=[base])
    await setup_integration(hass, mock_config_entry, client)

    unique_id = f"{DOMAIN}_base_{data.BASE_ID}_firmware"
    state = state_for(hass, "sensor", unique_id)
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "1.0.0"


# ---------------------------------------------------------------------------
# Skill deactivation/re-activation — bookkeeping must not re-add unique_ids
# ---------------------------------------------------------------------------


def _air_sensor_with_co2_active(active: bool):
    """The default air sensor with its CO2 skill flipped to ``active``."""
    from aranet_cloud import Skill

    air = data.build_air_sensor()
    air.skills = [
        Skill(metric=s.metric, active=active) if s.metric == data.M_CO2 else s
        for s in air.skills
    ]
    return air


async def test_metric_reactivation_does_not_duplicate_entity(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Deactivate a metric's skill, then re-activate it → no duplicate add.

    Regression: the platforms used to drop a deactivated metric's key from
    their ``known`` bookkeeping while the entity object remained, so
    re-activation re-ran async_add_entities with the same unique_id —
    "ID … already exists" registry errors on every occurrence.
    """
    coordinator = init_integration.runtime_data

    # Refresh 1: CO2 skill flips inactive (entity object remains in HA).
    mock_client.get_sensors.return_value = [
        _air_sensor_with_co2_active(False),
        data.build_soil_sensor(),
    ]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Refresh 2: the skill comes back.
    mock_client.get_sensors.return_value = data.build_sensors()
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert "already exists" not in caplog.text

    # Exactly one CO2 entity, still registered and still reporting.
    ent_reg = er.async_get(hass)
    entries = er.async_entries_for_config_entry(ent_reg, init_integration.entry_id)
    co2_uid = _uid(AIR, data.M_CO2)
    assert [e.unique_id for e in entries].count(co2_uid) == 1
    state = state_for(hass, "sensor", co2_uid)
    assert float(state.state) == pytest.approx(612.0)
