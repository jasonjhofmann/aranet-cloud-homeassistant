"""Constants for the Aranet Cloud integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "aranet_cloud"
DEFAULT_NAME: Final = "Aranet Cloud"
MANUFACTURER: Final = "Aranet"

CONF_API_KEY: Final = "api_key"

# Polling cadence. The Aranet Cloud has no documented rate limit and our
# Phase 0 probe showed 20 requests in 12.6 s were unbottled, but the
# underlying sensors only push at 1-minute intervals so polling faster than
# that yields no new data. 60 s is the sweet spot. Users can tune via the
# options flow once we ship that in Phase 3.
DEFAULT_SCAN_INTERVAL: Final = timedelta(seconds=60)

# Metric IDs as documented by the Aranet API. Listed centrally so the sensor
# platform (and future binary_sensor / image / etc. platforms) can reference
# them by intention rather than magic string.
class Metric:
    """Aranet metric IDs.

    Source: ``GET /api/v1/metrics`` on the production API as of Phase 0
    research. ``kind`` annotation indicates whether the metric appears in
    ``measurements/last`` (gauge) or ``telemetry/last`` (telemetry).
    """

    TEMPERATURE: Final = "1"          # gauge
    HUMIDITY: Final = "2"             # gauge
    CO2: Final = "3"                  # gauge
    ATMOSPHERIC_PRESSURE: Final = "4" # gauge
    VOLUMETRIC_WATER_CONTENT: Final = "8"   # gauge (soil)
    SOIL_DIELECTRIC_PERMITTIVITY: Final = "9"  # gauge (soil)
    SOIL_ELECTRICAL_CONDUCTIVITY: Final = "10"  # gauge (soil)
    PORE_ELECTRICAL_CONDUCTIVITY: Final = "11"  # gauge (soil)
    FRACTION: Final = "24"            # gauge
    VAPOUR_PRESSURE_DEFICIT: Final = "28"  # gauge
    DAY_LIGHT_INTEGRAL: Final = "29"  # gauge
    RSSI: Final = "61"                # telemetry
    BATTERY: Final = "62"             # telemetry
    BASE_STATUS: Final = "81"         # telemetry


# Phase 2 only ships the CO₂ entity to prove the wiring. Phase 3 expands
# to the full metric set.
PHASE2_ENABLED_METRICS: Final = frozenset({Metric.CO2})
