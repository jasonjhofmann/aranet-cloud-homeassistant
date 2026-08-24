# Aranet Cloud — Home Assistant integration

[![HACS Default](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://hacs.xyz/)
[![release](https://img.shields.io/github/v/release/jasonjhofmann/aranet-cloud-homeassistant?label=release&color=blue)](https://github.com/jasonjhofmann/aranet-cloud-homeassistant/releases)

Read all your [Aranet Cloud](https://aranet.cloud/) sensors into Home
Assistant via the official REST API. Works alongside (or instead of) the
built-in Bluetooth Aranet integration — and is the only path for sensors
that aren't in BLE range of your HA host.

> **Status:** Stable (1.0.0, Platinum quality scale). In the **HACS default
> repository**.

## What you get

- **One Home Assistant device per Aranet sensor**, grouped under a parent
  device for each base station — the same hierarchy you see in the Aranet app.
- **Sensors** for each supported metric your sensors report:
  temperature, humidity, CO₂, atmospheric pressure, volumetric water
  content, soil + pore electrical conductivity, soil dielectric permittivity,
  vapour-pressure deficit, day light integral, voltage, weight, distance,
  differential pressure, radon, fraction, RSSI (signal), and battery.
  (See [Supported metrics](https://github.com/jasonjhofmann/aranet-cloud-homeassistant#supported-metrics) — coverage is
  complete against the current Aranet Cloud catalog.)
- **Binary sensors** for the built-in Aranet alarm rules: per-sensor low
  battery, per-base-station offline.
- **Diagnostic entity** per base station showing firmware version.
- **Unit preservation** — values arrive in whatever units your Aranet
  account is configured to display (°F vs °C, mmHg vs hPa, etc.). Home
  Assistant's built-in conversions still work if you prefer something else.
- **Fixed 60-second poll cadence**, keeping pace with Aranet's fastest
  (1-minute) reporting interval. Not user-configurable per HA Core
  conventions — the integration owns its cadence.
- **Reauth flow** on revoked or rotated API keys.
- **Diagnostics download** with the API key automatically redacted —
  paste into a GitHub issue if something looks off.
- **Aranet branding** bundled in the integration (icon + logo in light + dark)
  via Home Assistant's Brands Proxy API (HA 2026.3+).

## Supported hardware

The integration is **catalog-driven**: it doesn't hard-code a list of sensor
models. It creates a Home Assistant device for any Aranet sensor on your
account that reports at least one metric it knows how to render (see
[Supported metrics](https://github.com/jasonjhofmann/aranet-cloud-homeassistant#supported-metrics) below), so new and Pro/virtual sensor
types appear automatically.

### Verified on real hardware

These types have been tested end-to-end against physical sensors:

- **Aranet4 (S4V1)** — 4-in-1 air quality (T, RH, CO₂, P)
- **Aranet legacy (S1V16)** — older 2-metric model
- **Soil moisture (S6V4)** — capacitive soil + temperature
- **Soil VWC / EC / T (S6V1)** — Delta-T WET150 multi-parameter probe

### Expected to work — not yet verified

The Aranet Cloud catalog lists ~53 sensor *types*. Every **metric** they can
report is rendered (see [Supported metrics](https://github.com/jasonjhofmann/aranet-cloud-homeassistant#supported-metrics)), but the
following device types haven't been exercised on physical hardware — for
example the **Aranet2 (S4V5)**, the **0–10 VDC / 4–20 mA transmitter bridges
(S5V1 / S5V2)**, the **Radon Plus PRO**, and Pro/virtual sensor types. They
should appear and work; if you have one, a
[diagnostics download](https://github.com/jasonjhofmann/aranet-cloud-homeassistant#reporting-issues) on an issue is very welcome.

## Supported metrics

The integration renders an entity for **every metric class in the Aranet Cloud
catalog**. A sensor gets a `sensor` entity for each of these it reports:

- temperature, humidity, CO₂, atmospheric pressure
- soil moisture (VWC), soil permittivity, soil EC, pore EC
- vapour-pressure deficit, day-light integral
- voltage, weight, distance, differential pressure
- radon, fraction
- signal strength, battery

(See [Entity reference](https://github.com/jasonjhofmann/aranet-cloud-homeassistant#entity-reference) for device classes and units.) Plus
the built-in **Low battery** / **Base station offline** binary sensors and a
per-base firmware diagnostic.

Coverage is complete against the current catalog. A *future* metric Aranet
adds would be skipped until added here — a one-row change to `METRIC_REGISTRY`
(see [CONTRIBUTING](CONTRIBUTING.md)). Units follow your Aranet account
preference (°C vs °F, hPa vs mmHg, …); an unrecognised unit shows the value
with no unit label.

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

### Via HACS (recommended)

Aranet Cloud is in the **HACS default repository** — no custom repository
needed.

1. In HACS, search for **Aranet Cloud** → Download
2. Restart Home Assistant
3. Settings → Devices & Services → **+ Add Integration** → Aranet Cloud
4. Paste your Aranet Cloud API key

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jasonjhofmann&repository=aranet-cloud-homeassistant&category=integration)

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
| `sensor` | Soil EC | — | mS/cm |
| `sensor` | Pore EC | — | mS/cm |
| `sensor` | Vapour-pressure deficit | `pressure` | kPa / hPa / Pa (account preference) |
| `sensor` | Day light integral | — | mol/m²/d or µmol/m²/d |
| `sensor` | Voltage | `voltage` | V or mV (account preference) |
| `sensor` | Weight | `weight` | kg or lb (account preference) |
| `sensor` | Distance | — | m / cm / ft / in / mm (account preference) |
| `sensor` | Differential pressure | — | Pa / mbar / mmH₂O (account preference) |
| `sensor` | Radon | — | Bq/m³ or pCi/L (account preference) |
| `sensor` | Fraction | — | (unitless) |
| `sensor` | Signal strength (RSSI) | `signal_strength` (diagnostic, disabled by default) | dBm |
| `sensor` | Battery | `battery` (diagnostic) | % |
| `sensor` | Base firmware | — (diagnostic) | version string |
| `binary_sensor` | Low battery | `battery` | `on` = low |
| `binary_sensor` | Base station | `connectivity` | `on` = connected |

Per-sensor `unique_id`s use the **device-printed hex serial** (e.g. `0AB12`),
not the cloud numeric ID — so those entity IDs survive any cloud-side
rekeying. The two base-station entities (base firmware, base station offline)
key on the cloud-assigned base ID instead, so they re-key if a base is deleted
and re-registered in Aranet Cloud.

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
sensor and base catalogs), not one per entity. Aranet sensors report to the
cloud on a per-sensor interval you set in the Aranet app (as fast as 1 minute,
up to 10), so polling every 60 s keeps pace with even the fastest setting and a
tighter cadence returns no new data. The integration's own poll interval is
fixed and not user-configurable, per HA Core conventions.

When a sensor newly appears in your account it gains entities on the next
poll; when one is removed from the account, its device is pruned
automatically. An individual entity also goes `unavailable` once its latest
reading (or a base station's last check-in) is more than ~20 minutes old, so a
dead or out-of-range sensor stops presenting its last value as live. If the API
key is rejected mid-run, all entities go `unavailable` and a reauthentication
prompt appears.

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
- **Bundled brand icons need HA 2026.3+.** The integration itself runs on
  HA 2025.1+ (the `hacs.json` floor); the in-repo Aranet icon/logo are served
  by Home Assistant's local Brands Proxy, which only exists on HA 2026.3+. On
  older cores the integration is fully functional but shows a generic icon.

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
- **A single entity is `unavailable` while its siblings are fine.** Each
  entity independently goes `unavailable` once its most recent reading is more
  than ~20 minutes old (a flat battery, or a sensor out of range of its base) —
  even while the coordinator keeps polling successfully and the tile shows no
  error. This is deliberate: a stale reading is suppressed rather than shown as
  a live value, so one lone `unavailable` entity points at that specific
  sensor, not the cloud connection.

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
- **Unrendered metrics** — `Sensor X reports metric id N … — skipping` (once
  per sensor/metric) if Aranet ever reports a metric this integration doesn't
  render yet. That's your cue to [open an issue](https://github.com/jasonjhofmann/aranet-cloud-homeassistant#reporting-issues) — adding it
  is a one-row change.
- **Device cleanup** — a one-line `INFO` (no debug needed) when a device is
  removed because the account stopped reporting it.

The API key is **never** logged at any level. Coordinator failures are
logged once when they start and once when they recover (Home Assistant's
standard coordinator behaviour), so a flaky connection won't spam the log.

## Reporting issues

Use the GitHub issue tracker linked from this README. Please include the
diagnostics download — the API key is redacted before the snapshot is
generated, so it's safe to share.

For intermittent problems, also enable debug logging (integration page →
⋮ → **Enable debug logging**, which now covers the `aranet-cloud` client
library too, or via YAML):

```yaml
logger:
  logs:
    custom_components.aranet_cloud: debug
    aranet_cloud: debug
```

Debug logs include per-poll counts (sensors/bases/readings/alarms) and the
client library's retry/timeout attempts; credentials never appear in logs.

## Architecture

- Backed by [`aranet-cloud`](https://github.com/jasonjhofmann/aranet-cloud),
  a standalone async Python library wrapping the Aranet Cloud REST API
  (25 of its 27 read-only GET endpoints). Reusable outside Home Assistant.
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
