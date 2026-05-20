# Aranet Cloud — Home Assistant integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
![version](https://img.shields.io/badge/version-0.3.0-blue.svg)

Read all your [Aranet Cloud](https://aranet.cloud/) sensors into Home
Assistant via the official REST API. Works alongside (or instead of) the
built-in Bluetooth Aranet integration — and is the only path for sensors
that aren't in BLE range of your HA host.

> **Status:** Pre-release (0.3.x). Functionally complete. v1.0 ships when
> submitted to the HACS default registry; until then, install as a custom
> repository.

## What you get

- **One Home Assistant device per Aranet sensor**, grouped under a parent
  device for each base station — the same hierarchy you see in the Aranet app.
- **Sensors** for every metric your sensors report:
  temperature, humidity, CO₂, atmospheric pressure, volumetric water
  content, soil + pore electrical conductivity, soil dielectric permittivity,
  vapour-pressure deficit, day light integral, RSSI (signal), battery.
- **Binary sensors** for the built-in Aranet alarm rules: per-sensor low
  battery, per-base-station offline.
- **Diagnostic entity** per base station showing firmware version.
- **Unit preservation** — values arrive in whatever units your Aranet
  account is configured to display (°F vs °C, mmHg vs hPa, etc.). Home
  Assistant's built-in conversions still work if you prefer something else.
- **Options flow** for tuning the poll cadence (30–600 s, default 60 s).
- **Reauth flow** on revoked or rotated API keys.
- **Diagnostics download** with the API key automatically redacted —
  paste into a GitHub issue if something looks off.
- **Aranet branding** bundled in the integration (icon + logo in light + dark)
  via Home Assistant's Brands Proxy API (HA 2026.3+).

## Supported hardware

All sensor types in the Aranet Cloud catalog work — the integration is
driven by what your account actually reports, not a hard-coded sensor list.
Tested against:

- **Aranet4 (S4V1)** — 4-in-1 air quality (T, RH, CO₂, P)
- **Aranet2 (S4V5)** — lower-tier air quality
- **Aranet legacy (S1V16)** — older 2-metric model
- **Soil moisture S6V4** — capacitive soil + temp
- **Soil VWC, EC and T (S6V1)** — Delta-T WET150 multi-parameter probe
- **0–10 VDC / 4–20 mA transmitters (S5V1 / S5V2)** — industrial input bridges

The Aranet Cloud catalog lists 53 sensor types in total; any of them
should surface in HA with whatever metrics they report. If your sensor
type isn't recognised, it still shows up as a device — just without the
type-specific cosmetics.

## Installation

### Via HACS (custom repository)

1. HACS → Integrations → ⋮ menu → **Custom repositories**
2. URL: `https://github.com/jasonjhofmann/aranet-cloud-homeassistant`
3. Category: **Integration**
4. Find "Aranet Cloud" in the list → Download
5. Restart Home Assistant
6. Settings → Devices & Services → **+ Add Integration** → Aranet Cloud
7. Paste your Aranet Cloud API key

### Manually

1. Copy `custom_components/aranet_cloud/` into your HA
   `/config/custom_components/`
2. Restart HA (the [`aranet-cloud`](https://pypi.org/project/aranet-cloud/)
   Python dependency is installed automatically from `manifest.json`)
3. Add the integration via the UI as above

## Getting an API key

1. Sign in to [aranet.cloud](https://aranet.cloud/)
2. Account → API
3. Generate a key
4. Paste into the integration setup form

The integration is **read-only** — it only ever calls `GET` endpoints. No
data is written to your Aranet account.

## Entity reference

| Domain | Metric | HA device class | Default unit |
|---|---|---|---|
| `sensor` | Temperature | `temperature` | °C or °F (account preference) |
| `sensor` | Humidity | `humidity` | % |
| `sensor` | CO₂ | `carbon_dioxide` | ppm |
| `sensor` | Atmospheric pressure | `atmospheric_pressure` | mmHg / hPa / inHg (account preference) |
| `sensor` | Soil moisture (VWC) | `moisture` | % |
| `sensor` | Soil permittivity | — | (unitless) |
| `sensor` | Soil EC | — | S/m or mS/cm |
| `sensor` | Pore EC | — | S/m or mS/cm |
| `sensor` | Vapour-pressure deficit | `pressure` | kPa / hPa / Pa |
| `sensor` | Day light integral | — | mol/m²/d |
| `sensor` | Signal strength (RSSI) | `signal_strength` (diagnostic) | dBm |
| `sensor` | Battery | `battery` (diagnostic) | % |
| `sensor` | Base firmware | — (diagnostic) | version string |
| `binary_sensor` | Low battery | `battery` | `on` = low |
| `binary_sensor` | Base station | `connectivity` | `on` = connected |

All `unique_id`s use the **device-printed hex serial** (e.g. `02D0C`),
not the cloud numeric ID — so entity IDs survive any cloud-side rekeying.

## Configuration

After initial setup, click **Configure** on the integration tile to access
runtime options:

- **Polling interval (seconds):** how often to refresh. Default 60 s. The
  Aranet sensors themselves push roughly once per minute, so polling much
  faster yields no new data. Range: 30–600 s.

## Troubleshooting

### "Could not connect to Aranet Cloud" during setup

- Check your internet connection.
- Verify `https://aranet.cloud/api/v1/sensors` is reachable from your HA
  host (try `curl -H "ApiKey: yours" …`).
- Some corporate networks block Cloudflare-fronted endpoints — the API
  sits behind Cloudflare.

### "The API key was rejected"

- Make sure you copied the full key without trailing whitespace.
- Confirm the key wasn't revoked in the Aranet Cloud dashboard.
- If you recently rotated, the integration will surface a Repairs entry
  prompting you to paste the new key.

### Entities show `unavailable`

- Check the integration tile for setup errors.
- Click **Download diagnostics** and inspect the `coordinator.last_update_success`
  flag and the raw snapshot — the API key is auto-redacted.
- The Aranet sensors themselves go silent when out of range of their
  base station; check the RSSI entity (low values mean weak signal).

## Reporting issues

Use the GitHub issue tracker linked from this README. Please include the
diagnostics download — the API key is redacted before the snapshot is
generated, so it's safe to share.

## Architecture

- Backed by [`aranet-cloud`](https://github.com/jasonjhofmann/aranet-cloud),
  a standalone async Python library covering the full 27-endpoint API
  surface. Reusable outside Home Assistant.
- Single `DataUpdateCoordinator` polls measurements, telemetry, and
  alarms each cycle; base + sensor catalogs are refreshed in the same
  cycle (cheap, stable).
- Base devices are pre-registered before sensor entities, so the
  `via_device` device-hierarchy link is set up correctly per HA 2025.12+
  rules.
- Brand assets are bundled in `custom_components/aranet_cloud/brand/`
  via HA's new Brands Proxy API (no PR to home-assistant/brands required).

## License

Apache 2.0. The integration uses the [official Aranet brand assets](https://github.com/home-assistant/brands/tree/master/core_integrations/aranet)
from the Home Assistant brands repository, contributed by Aranet (SAF Tehnika).
