"""Builders for synthetic ``aranet-cloud`` model objects used across tests.

These construct the same dataclasses the real library returns, so tests
exercise the integration's handling of genuine model instances (not dicts).
Identifiers are synthetic — no real-fleet serials or MACs.
"""

from __future__ import annotations

from datetime import UTC, datetime

from aranet_cloud import Alarm, Base, Pairing, Reading, Sensor, Skill

# A fixed timestamp so tests never depend on wall-clock time.
FIXED_TIME = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)

BASE_ID = "100000000001"
AIR_SENSOR_ID = "4205836"
AIR_SENSOR_SERIAL = "0AA01"
SOIL_SENSOR_ID = "4205900"
SOIL_SENSOR_SERIAL = "0BB02"

# Metric IDs (mirrors const.Metric — duplicated here to keep tests independent).
M_TEMPERATURE = "1"
M_HUMIDITY = "2"
M_CO2 = "3"
M_PRESSURE = "4"
M_SOIL_VWC = "8"
M_SOIL_PERMITTIVITY = "9"
M_SOIL_EC = "10"
M_PORE_EC = "11"
M_RSSI = "61"
M_BATTERY = "62"
M_BASE_STATUS = "81"
# Additional catalog metrics (specialty / Pro / transmitter sensors).
M_VOLTAGE = "5"
M_WEIGHT = "7"
M_DISTANCE = "13"
M_DIFF_PRESSURE = "17"
M_FRACTION = "24"
M_RADON = "30"

SPECIALTY_SENSOR_ID = "4205950"
SPECIALTY_SENSOR_SERIAL = "0CC03"


def build_base(*, base_id: str = BASE_ID, name: str = "Aranet-1a2b3c") -> Base:
    """A single base station."""
    return Base(
        id=base_id,
        name=name,
        firmware="1.0.0",
        product="Aranet PRO",
        board="rev-c",
        region="EU",
        registered_at=FIXED_TIME,
        last_seen=FIXED_TIME,
    )


def _skills(*metrics: str) -> list[Skill]:
    return [Skill(metric=m, active=True) for m in metrics]


def build_air_sensor() -> Sensor:
    """An Aranet4-style air sensor reporting T/RH/CO2/P + telemetry."""
    return Sensor(
        id=AIR_SENSOR_ID,
        serial=AIR_SENSOR_SERIAL,
        name="Living Room",
        type="S4V1",
        skills=_skills(M_TEMPERATURE, M_HUMIDITY, M_CO2, M_PRESSURE, M_RSSI, M_BATTERY),
        pairings=[Pairing(base=BASE_ID, paired_at=FIXED_TIME, removed_at=None)],
    )


def build_soil_sensor() -> Sensor:
    """A soil probe reporting the soil-metric family + telemetry."""
    return Sensor(
        id=SOIL_SENSOR_ID,
        serial=SOIL_SENSOR_SERIAL,
        name="Garden Bed",
        type="S6V4",
        skills=_skills(
            M_SOIL_VWC,
            M_SOIL_PERMITTIVITY,
            M_SOIL_EC,
            M_PORE_EC,
            M_RSSI,
            M_BATTERY,
        ),
        pairings=[Pairing(base=BASE_ID, paired_at=FIXED_TIME, removed_at=None)],
    )


def build_specialty_sensor() -> Sensor:
    """A sensor exercising the additional catalog metrics (voltage/weight/etc.)."""
    return Sensor(
        id=SPECIALTY_SENSOR_ID,
        serial=SPECIALTY_SENSOR_SERIAL,
        name="Test Rig",
        type="S5V1",
        skills=_skills(
            M_VOLTAGE, M_WEIGHT, M_DISTANCE, M_DIFF_PRESSURE, M_RADON, M_FRACTION
        ),
        pairings=[Pairing(base=BASE_ID, paired_at=FIXED_TIME, removed_at=None)],
    )


def build_specialty_readings() -> list[Reading]:
    """Gauge readings for the specialty sensor, one per added metric."""
    return [
        _reading(SPECIALTY_SENSOR_ID, M_VOLTAGE, "5", 3.3),  # V
        _reading(SPECIALTY_SENSOR_ID, M_WEIGHT, "7", 12.5),  # kg
        _reading(SPECIALTY_SENSOR_ID, M_DISTANCE, "10", 1.42),  # m
        _reading(SPECIALTY_SENSOR_ID, M_DIFF_PRESSURE, "131", 25.0),  # Pa
        _reading(SPECIALTY_SENSOR_ID, M_RADON, "23", 48.0),  # Bq/m³
        _reading(SPECIALTY_SENSOR_ID, M_FRACTION, "18", 0.5),  # unitless
    ]


def build_sensors() -> list[Sensor]:
    """The default two-sensor fleet."""
    return [build_air_sensor(), build_soil_sensor()]


def _reading(sensor_id: str, metric: str, unit: str, value: float) -> Reading:
    return Reading(
        sensor=sensor_id, metric=metric, unit=unit, value=value, time=FIXED_TIME
    )


def build_measurement_readings() -> list[Reading]:
    """Gauge readings (the ``measurements/last`` plane)."""
    return [
        _reading(AIR_SENSOR_ID, M_TEMPERATURE, "1", 22.7),
        _reading(AIR_SENSOR_ID, M_HUMIDITY, "2", 41.0),
        _reading(AIR_SENSOR_ID, M_CO2, "3", 612.0),
        _reading(AIR_SENSOR_ID, M_PRESSURE, "4", 98500.0),
        _reading(SOIL_SENSOR_ID, M_SOIL_VWC, "2", 27.5),
        _reading(SOIL_SENSOR_ID, M_SOIL_PERMITTIVITY, "18", 14.2),
        _reading(SOIL_SENSOR_ID, M_SOIL_EC, "8", 0.123),
        _reading(SOIL_SENSOR_ID, M_PORE_EC, "8", 0.456),
    ]


def build_telemetry_readings() -> list[Reading]:
    """Telemetry readings (the ``telemetry/last`` plane: RSSI + battery)."""
    return [
        _reading(AIR_SENSOR_ID, M_RSSI, "11", -67.0),
        _reading(AIR_SENSOR_ID, M_BATTERY, "115", 94.0),
        _reading(SOIL_SENSOR_ID, M_RSSI, "11", -71.0),
        _reading(SOIL_SENSOR_ID, M_BATTERY, "115", 88.0),
    ]


def build_low_battery_alarm(sensor_id: str = AIR_SENSOR_ID) -> Alarm:
    """An active low-battery alarm for the given sensor."""
    return Alarm(
        id="alarm-batt-1",
        sensor=sensor_id,
        metric=M_BATTERY,
        unit="115",
        rule="rule-low-battery",
        severity=2,
        threshold="10",
        value=8.0,
        worst=8.0,
        alarmed_at=FIXED_TIME,
        resolved_at=None,
    )


def build_base_offline_alarm(base_id: str = BASE_ID) -> Alarm:
    """An active base-station-offline alarm (its ``sensor`` field is the base)."""
    return Alarm(
        id="alarm-offline-1",
        sensor=base_id,
        metric=M_BASE_STATUS,
        unit="",
        rule="rule-base-offline",
        severity=3,
        threshold="",
        value=0.0,
        worst=0.0,
        alarmed_at=FIXED_TIME,
        resolved_at=None,
    )
