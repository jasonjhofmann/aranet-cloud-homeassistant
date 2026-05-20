"""Constants for the Aranet Cloud integration.

Includes the metric and unit ID catalogs that drive the sensor + binary_sensor
platforms — both are exhaustive against the Aranet Cloud API as of Phase 0
research (see ``docs/architecture.md`` in the ``aranet-cloud`` library repo
for ground truth).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "aranet_cloud"
DEFAULT_NAME: Final = "Aranet Cloud"
MANUFACTURER: Final = "Aranet"

CONF_API_KEY: Final = "api_key"
CONF_SCAN_INTERVAL: Final = "scan_interval"

# Polling cadence. Aranet sensors push once a minute, so 60 s is the sweet
# spot — faster yields no new data, slower drops responsiveness.
DEFAULT_SCAN_INTERVAL_SECONDS: Final = 60
MIN_SCAN_INTERVAL_SECONDS: Final = 30
MAX_SCAN_INTERVAL_SECONDS: Final = 600
DEFAULT_SCAN_INTERVAL: Final = timedelta(seconds=DEFAULT_SCAN_INTERVAL_SECONDS)


class Metric:
    """Aranet metric IDs (source: ``GET /api/v1/metrics``).

    ``kind`` annotations indicate whether a metric appears in
    ``measurements/last`` (``g`` gauge) or ``telemetry/last`` (``t`` telemetry).
    """

    TEMPERATURE: Final = "1"               # gauge
    HUMIDITY: Final = "2"                  # gauge
    CO2: Final = "3"                       # gauge
    ATMOSPHERIC_PRESSURE: Final = "4"      # gauge
    VOLUMETRIC_WATER_CONTENT: Final = "8"  # gauge (soil VWC)
    SOIL_DIELECTRIC_PERMITTIVITY: Final = "9"   # gauge (soil)
    SOIL_ELECTRICAL_CONDUCTIVITY: Final = "10"  # gauge (soil)
    PORE_ELECTRICAL_CONDUCTIVITY: Final = "11"  # gauge (soil)
    FRACTION: Final = "24"                 # gauge (rarely seen)
    VAPOUR_PRESSURE_DEFICIT: Final = "28"  # gauge (greenhouse)
    DAY_LIGHT_INTEGRAL: Final = "29"       # gauge (greenhouse)
    RSSI: Final = "61"                     # telemetry
    BATTERY: Final = "62"                  # telemetry
    BASE_STATUS: Final = "81"              # telemetry (base-station only)


# Unit-ID → HA unit-of-measurement mapping.
#
# The Aranet API attaches a unit ID to every reading. Multiple unit IDs can
# map to the same physical unit (e.g. ``1`` and ``119`` both = Celsius); the
# table below covers every unit we have ever observed in the metrics catalog.
# Unknown units fall back to the raw API name via :func:`unit_for_id`.
#
# Pulled from ``GET /api/v1/metrics`` on the production API; see
# ``docs/architecture.md`` for the full enumeration.
UNIT_BY_ID: Final[dict[str, str]] = {
    # temperature
    "1": "°C",
    "119": "°C",
    "101": "°F",
    "102": "K",
    # humidity / fractions / percentages
    "2": "%",
    "120": "%RH",
    "132": "%",
    "115": "%",
    "122": "/",
    "123": "/",
    "18": "",
    "130": "",
    # CO₂
    "3": "ppm",
    # atmospheric / VPD pressures
    "4": "Pa",
    "21": "Pa",
    "117": "atm",
    "105": "bar",
    "136": "bar",
    "104": "hPa",
    "135": "hPa",
    "134": "kPa",
    "114": "inHg",
    "103": "mmHg",
    "106": "psi",
    "137": "psi",
    # signal strength
    "11": "dBm",
    "121": "dBW",
    # electrical conductivity (soil)
    "8": "S/m",
    "108": "mS/cm",
    # voltage
    "16": "V",
    # day light integral
    "22": "µmol/m²/d",
    "140": "mol/m²/d",
    "142": "mol/m2/d",
}


def unit_for_id(unit_id: str, fallback: str = "") -> str:
    """Look up an Aranet unit ID; return ``fallback`` when unknown."""
    return UNIT_BY_ID.get(unit_id, fallback)


# Built-in alarm rule metric IDs — the two rules every Aranet account has
# out of the box. User-created rules can target any metric and are handled
# generically by the binary_sensor platform.
BUILTIN_ALARM_METRICS: Final = frozenset({Metric.BATTERY, Metric.BASE_STATUS})
