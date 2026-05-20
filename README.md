# Aranet Cloud — Home Assistant integration

Read all your [Aranet Cloud](https://aranet.cloud/) sensors into Home
Assistant via the official REST API. Works alongside (or instead of) the
built-in Bluetooth Aranet integration — and is the only path for sensors
that aren't in BLE range of your HA host.

> **Status:** Pre-release (0.1.x). Phase 2 of a phased rollout — ships
> CO₂ entities for Aranet4 sensors only as a proof of wiring. Phase 3
> expands to the full metric set (temperature, humidity, pressure, soil
> moisture, battery, RSSI, etc.) plus alarms.

## Features (Phase 2)

- UI-configured (no YAML) — Settings → Devices & Services → "+ Add" → Aranet Cloud
- Reauth flow on revoked/rotated API keys
- One device per Aranet sensor, model + serial visible in the device registry
- `sensor.<sensor_name>_co2` entity per CO₂-capable sensor, polled at 60 s

## Roadmap

- **Phase 3:** all 14 metric types (T, RH, P, VWC, EC, RSSI, battery, …),
  base stations as devices, alarms as binary_sensors, diagnostics platform,
  repairs flow for revoked keys, options flow for tunable poll cadence.
- **Phase 4:** documentation polish, HACS default-registry submission,
  v1.0 release.

## Installation

### Via HACS (custom repository — until accepted into the default registry)

1. HACS → Integrations → ⋮ → Custom repositories
2. Add `https://github.com/jasonjhofmann/aranet-cloud-homeassistant` as
   category "Integration"
3. Find "Aranet Cloud" in the list, click Download
4. Restart Home Assistant
5. Settings → Devices & Services → + Add Integration → Aranet Cloud

### Manually

1. Copy `custom_components/aranet_cloud/` into your HA `/config/custom_components/`
2. Ensure the [`aranet-cloud`](https://pypi.org/project/aranet-cloud/) Python
   package is installed in HA's environment (HA does this automatically on
   first load via `manifest.json` `requirements`)
3. Restart HA, then add the integration via the UI

## Configuration

You'll need an Aranet Cloud API key. Generate one from your Aranet Cloud
dashboard under **Account → API**. The integration only ever reads — no
writes happen against your Aranet account.

## Architecture

- Backed by [`aranet-cloud`](https://github.com/jasonjhofmann/aranet-cloud),
  a standalone async Python library covering the full 27-endpoint API surface.
- Single `DataUpdateCoordinator` for Phase 2; will split into a fast
  (measurements/telemetry) and slow (catalog) pair in Phase 3.
- All entity `unique_id`s use the device-printed hex **serial** (not the
  cloud numeric ID) so they survive cloud-side rekeying.

## License

Apache 2.0
