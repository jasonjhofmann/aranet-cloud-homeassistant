# Aranet Cloud — Home Assistant integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![release](https://img.shields.io/github/v/release/jasonjhofmann/aranet-cloud-homeassistant?label=release&color=blue)](https://github.com/jasonjhofmann/aranet-cloud-homeassistant/releases)

Read all your [Aranet Cloud](https://aranet.cloud/) sensors into Home
Assistant via the official REST API. Works alongside (or instead of) the
built-in Bluetooth Aranet integration — and is the only path for sensors
that aren't in BLE range of your HA host.

> **Status:** Pre-release (0.6.x, Platinum quality scale). Functionally complete. v1.0 ships when
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
- **Fixed 60-second poll cadence**, matching Aranet sensors' 60 s sample
  rate. Not user-configurable per HA Core conventions — the integration
  owns its cadence.
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

## Use cases

- **Whole-home air quality** — pull every Aranet4/Aranet2 CO₂, temperature,
  humidity, and pressure reading into HA, even for sensors that are nowhere
  near your HA host's Bluetooth range (the cloud is the transport).
- **Greenhouse / grow rooms** — VPD and daily-light-integral entities feed
  climate and lighting automations.
- **Soil & irrigation** — soil moisture (VWC), permittivity, and EC from
  S6V4 / WET150 probes drive watering logic and long-term statistics.
- **Fleet health at a glance** — per-sensor battery and signal-strength
  diagnostics plus low-battery and base-offline binary sensors let you
  alert before a sensor silently drops out.

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

## Removing the integration

This integration follows standard Home Assistant removal — no extra steps.

1. Go to **Settings → Devices & Services**.
2. Click the **Aranet Cloud** integration entry.
3. Use the **⋮** (three-dot) menu on the entry and choose **Delete**.

Deleting the config entry removes all of the integration's devices and
entities and discards the stored API key. To remove the integration's code
as well, open **HACS → Aranet Cloud → ⋮ → Remove** (or delete
`custom_components/aranet_cloud/` if you installed manually), then restart
Home Assistant. Your Aranet Cloud account is untouched — the integration is
read-only and never modifies it.

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
| `sensor` | Signal strength (RSSI) | `signal_strength` (diagnostic, disabled by default) | dBm |
| `sensor` | Battery | `battery` (diagnostic) | % |
| `sensor` | Base firmware | — (diagnostic) | version string |
| `binary_sensor` | Low battery | `battery` | `on` = low |
| `binary_sensor` | Base station | `connectivity` | `on` = connected |

All `unique_id`s use the **device-printed hex serial** (e.g. `0AB12`),
not the cloud numeric ID — so entity IDs survive any cloud-side rekeying.

## Example automations

Alert when a room's CO₂ climbs above 1000 ppm:

```yaml
automation:
  - alias: "High CO₂ — Living Room"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.living_room_co2
        above: 1000
    actions:
      - action: notify.mobile_app_phone
        data:
          message: "Living Room CO₂ is {{ states('sensor.living_room_co2') }} ppm — ventilate."
```

Notify when a sensor reports low battery, or a base station drops offline:

```yaml
automation:
  - alias: "Aranet sensor needs attention"
    triggers:
      - trigger: state
        entity_id: binary_sensor.living_room_low_battery
        to: "on"
      - trigger: state
        entity_id: binary_sensor.aranet_1a2b3c_base_station
        to: "off"   # connectivity class: off = disconnected
    actions:
      - action: notify.mobile_app_phone
        data:
          message: "An Aranet device needs attention."
```

## How data is updated

The integration **polls** Aranet Cloud once every **60 seconds** through a
single `DataUpdateCoordinator` shared by all entities — one set of API calls
per cycle (`measurements/last`, `telemetry/last`, `alarms/actual`, plus the
sensor and base catalogs), not one per entity. Aranet sensors themselves
report to the cloud roughly once a minute, so a faster cadence returns no
new data; the interval is fixed and not user-configurable.

When a sensor newly appears in your account it gains entities on the next
poll; when one is removed from the account, its device is pruned
automatically. If the API key is rejected mid-run, all entities go
`unavailable` and a reauthentication prompt appears.

## Configuration

There is nothing to configure beyond the API key entered at setup. The poll
cadence is a fixed **60 seconds** (see *How data is updated*) and is
intentionally not user-tunable, per Home Assistant Core conventions (the
integration owns its cadence).

If your API key is rotated or revoked, the integration triggers a
reauthentication prompt so you can paste the new key. To change the key
proactively, use the integration entry's **⋮ → Reconfigure** action.

## Known limitations

- **Cloud-only.** This integration talks to the Aranet *Cloud* REST API; it
  does not read sensors over Bluetooth. A working internet connection and a
  cloud-synced Aranet base station are required. For local BLE, use the
  built-in `aranet` integration instead (the two can run side by side).
- **Read-only.** Only `GET` endpoints are used — you cannot change sensor or
  account settings from Home Assistant.
- **Fixed 60 s cadence.** Sub-minute resolution is not available (and the
  upstream sample rate wouldn't supply it anyway).
- **User-defined alarm rules** beyond the built-in low-battery and
  base-offline rules are not yet surfaced as binary sensors.
- **Units follow your Aranet account preference** (°C vs °F, hPa vs mmHg,
  etc.); Home Assistant's own unit conversion can override the display.

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
- If you recently rotated, the integration shows a reauthentication prompt
  (Settings → Devices & Services) so you can paste the new key.

### Entities show `unavailable`

- Check the integration tile for setup errors.
- Click **Download diagnostics** and inspect the `coordinator.last_update_success`
  flag and the raw snapshot — the API key is auto-redacted.
- The Aranet sensors themselves go silent when out of range of their base
  station. Enable the per-sensor **Signal strength** entity (it's a
  diagnostic, disabled by default) to watch for a weak signal.

### Enabling debug logs

Add this to `configuration.yaml` and restart (or call the
`logger.set_level` service for a no-restart change):

```yaml
logger:
  logs:
    custom_components.aranet_cloud: debug
    aranet_cloud: debug   # the underlying REST client library
```

At `debug` you'll see, in `Settings → System → Logs`:

- **Setup** — the entry name, sensor/base counts, and poll interval.
- **Each poll** — `Polled Aranet Cloud: N sensor(s), N base(s), …` once per
  cycle, so you can confirm data is flowing and how much.
- **Entity changes** — `Adding N sensor entit…: <unique_id>, …` whenever a
  new sensor or metric appears.
- **Device cleanup** — a one-line `INFO` (no debug needed) when a device is
  removed because the account stopped reporting it.

The API key is **never** logged at any level. Coordinator failures are
logged once when they start and once when they recover (Home Assistant's
standard coordinator behaviour), so a flaky connection won't spam the log.

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

Apache 2.0. Aranet branding is bundled in-repo at
`custom_components/aranet_cloud/brand/` and served by Home Assistant's Brands
Proxy API (HA 2026.3+); "Aranet" is a trademark of SAF Tehnika.
