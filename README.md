# Aranet Cloud for Home Assistant

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/jasonjhofmann/aranet-cloud-homeassistant/main/custom_components/aranet_cloud/brand/dark_logo@2x.png">
  <img src="https://raw.githubusercontent.com/jasonjhofmann/aranet-cloud-homeassistant/main/custom_components/aranet_cloud/brand/logo@2x.png" alt="Aranet" width="240">
</picture>

[![release](https://img.shields.io/github/v/release/jasonjhofmann/aranet-cloud-homeassistant?label=release&color=blue)](https://github.com/jasonjhofmann/aranet-cloud-homeassistant/releases)
[![HACS Default](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://hacs.xyz/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![CI](https://github.com/jasonjhofmann/aranet-cloud-homeassistant/actions/workflows/ci.yml/badge.svg)](https://github.com/jasonjhofmann/aranet-cloud-homeassistant/actions/workflows/ci.yml)

Read every sensor on your [Aranet Cloud](https://aranet.cloud/) account into
Home Assistant through the official REST API.

The built-in `aranet` integration reads sensors over Bluetooth. This one reads
them over the cloud, so it also covers sensors that are nowhere near your Home
Assistant host. The two run side by side.

The integration is read-only. It calls `GET` endpoints and writes nothing to
your Aranet account.

> Unofficial. Not affiliated with or endorsed by SAF Tehnika.

## What you get

- **One Home Assistant device per sensor**, grouped under a parent device for
  its base station, matching the hierarchy in the Aranet app.
- **A sensor entity for every metric** in the Aranet Cloud catalog that your
  hardware reports. See [Entity reference](#entity-reference).
- **Binary sensors** for the two built-in Aranet alarm rules: low battery per
  sensor, and offline per base station.
- **A firmware diagnostic** per base station.
- **Units that follow your Aranet account preference**, so °F stays °F and
  mmHg stays mmHg. Home Assistant's own conversion still works if you'd rather
  see something else.
- **Reauthentication** when an API key is rotated or revoked.
- **A diagnostics download** with the API key redacted, ready to attach to a
  GitHub issue.

## Before you begin

You need the following:

- Home Assistant 2025.1.0 or later. Bundled Aranet branding needs 2026.3 or
  later; on older cores the integration works normally but shows a generic
  icon.
- An Aranet Cloud account with a cloud-synced base station.
- An Aranet Cloud API key.

### Get an API key

1. Sign in at [aranet.cloud](https://aranet.cloud/).
2. Go to **Account > API**.
3. Generate a key and copy it.

## Install

### Install with HACS

Aranet Cloud is in the HACS default repository, so you don't need to add a
custom repository.

1. In HACS, search for **Aranet Cloud** and download it.
2. Restart Home Assistant.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jasonjhofmann&repository=aranet-cloud-homeassistant&category=integration)

### Install manually

1. Copy `custom_components/aranet_cloud/` into your Home Assistant
   `config/custom_components/` directory.
2. Restart Home Assistant. The
   [`aranet-cloud`](https://pypi.org/project/aranet-cloud/) Python dependency
   installs automatically from `manifest.json`.

## Add the integration

1. Go to **Settings > Devices & services > Add integration** and select
   **Aranet Cloud**.
2. Paste your API key.
3. Click **Submit**.

There's nothing else to configure. The poll cadence is fixed, and Home
Assistant discovers your sensors and base stations on the first poll.

To replace the key before it's revoked, select **⋮ > Reconfigure** on the
config entry. If a key is rejected mid-run, Home Assistant prompts you to
reauthenticate on its own.

## Supported hardware

The integration is catalog-driven. It doesn't carry a list of sensor models.
Any Aranet sensor on your account that reports at least one metric the
integration knows how to render becomes a Home Assistant device, so new and
virtual sensor types appear on their own.

### Verified on physical hardware

- **Aranet4 (S4V1)**, the 4-in-1 air-quality sensor
- **Aranet legacy (S1V16)**, the older two-metric model
- **Soil moisture (S6V4)**, capacitive soil plus temperature
- **Soil VWC, EC, and temperature (S6V1)**, the Delta-T WET150 probe

### Expected to work, not yet verified

The Aranet Cloud catalog lists roughly 53 sensor types, and every metric they
can report is rendered. The types below haven't been exercised against physical
hardware:

- **Aranet2 (S4V5)**
- **Transmitter bridges (S5V1, S5V2)**, 0 to 10 VDC and 4 to 20 mA
- **Radon Plus PRO**
- Pro and virtual sensor types

They should appear and work. If you own one, a diagnostics download attached to
an issue is welcome. See [Report an issue](#report-an-issue).

## Entity reference

| Domain | Metric | Device class | Default unit |
| --- | --- | --- | --- |
| `sensor` | Temperature | `temperature` | °C or °F, per account preference |
| `sensor` | Humidity | `humidity` | % |
| `sensor` | Carbon dioxide | `carbon_dioxide` | ppm |
| `sensor` | Atmospheric pressure | `atmospheric_pressure` | mmHg, hPa, or inHg, per account preference |
| `sensor` | Soil moisture (VWC) | `moisture` | % |
| `sensor` | Soil permittivity | None | Unitless |
| `sensor` | Soil electrical conductivity | None | mS/cm |
| `sensor` | Pore electrical conductivity | None | mS/cm |
| `sensor` | Vapor-pressure deficit | `pressure` | kPa, hPa, or Pa, per account preference |
| `sensor` | Day light integral | None | mol/m²/d or µmol/m²/d |
| `sensor` | Voltage | `voltage` | V or mV, per account preference |
| `sensor` | Weight | `weight` | kg or lb, per account preference |
| `sensor` | Distance | None | m, cm, ft, in, or mm, per account preference |
| `sensor` | Differential pressure | None | Pa, mbar, or mmH₂O, per account preference |
| `sensor` | Radon | None | Bq/m³ or pCi/L, per account preference |
| `sensor` | Fraction | None | Unitless |
| `sensor` | Signal strength (RSSI) | `signal_strength`, diagnostic, disabled by default | dBm |
| `sensor` | Battery | `battery`, diagnostic | % |
| `sensor` | Base firmware | None, diagnostic | Version string |
| `binary_sensor` | Low battery | `battery` | `on` means low |
| `binary_sensor` | Base station | `connectivity` | `on` means connected |

Coverage is complete against the current Aranet Cloud catalog. If Aranet adds a
metric later, the integration skips it and logs a line at debug level until
it's added here, which is a one-row change to `METRIC_REGISTRY`. See
[CONTRIBUTING.md](CONTRIBUTING.md).

An unrecognized unit shows the value with no unit label rather than guessing.

### Entity ID stability

Per-sensor unique IDs use the hex serial printed on the device, such as
`0AB12`, rather than the cloud's numeric ID. Those entity IDs survive
cloud-side rekeying.

The two base-station entities key on the cloud-assigned base ID instead, so
they re-key if you delete a base and register it again in Aranet Cloud.

## How data is updated

One `DataUpdateCoordinator`, shared by every entity, polls Aranet Cloud every
60 seconds. Each cycle makes one set of API calls (`measurements/last`,
`telemetry/last`, `alarms/actual`, and the sensor and base catalogs) rather
than one call per entity.

Aranet sensors report to the cloud on a per-sensor interval you set in the
Aranet app, as fast as every minute and as slow as every 10. A 60-second poll
keeps pace with the fastest setting, and polling harder returns no new data.
The interval is fixed and isn't user-configurable, following Home Assistant
Core convention.

A sensor that newly appears on your account gains entities on the next poll. A
sensor removed from the account has its device pruned automatically, but only
after it's been missing from three consecutive polls, so a partial cloud
response can't delete your fleet.

### Stale readings go unavailable

An individual entity goes `unavailable` once its most recent reading, or a base
station's last check-in, is more than 20 minutes old. Twenty minutes is twice
the coarsest reporting interval the hardware offers, which leaves room for a
missed cycle.

This is deliberate. A dead or out-of-range sensor stops presenting its last
value as if it were live, and one lone `unavailable` entity points at that
sensor rather than at your cloud connection.

## Use cases

- **Whole-home air quality.** Pull CO₂, temperature, humidity, and pressure
  from every Aranet4 and Aranet2 into Home Assistant, including sensors far
  outside the host's Bluetooth range.
- **Greenhouses and grow rooms.** Vapor-pressure deficit and day light integral
  entities feed climate and lighting automations.
- **Soil and irrigation.** Soil moisture, permittivity, and electrical
  conductivity from S6V4 and WET150 probes drive watering logic and long-term
  statistics.
- **Fleet health.** Battery and signal-strength diagnostics, plus the
  low-battery and base-offline binary sensors, let you catch a sensor before it
  goes quiet.

## Automation examples

Notify when a room's CO₂ climbs above 1000 ppm:

```yaml
automation:
  - alias: "High CO2 in the living room"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.living_room_co2
        above: 1000
    actions:
      - action: notify.mobile_app_phone
        data:
          message: "Living room CO2 is {{ states('sensor.living_room_co2') }} ppm. Ventilate."
```

Notify when a sensor reports low battery or a base station drops offline:

```yaml
automation:
  - alias: "Aranet device needs attention"
    triggers:
      - trigger: state
        entity_id: binary_sensor.living_room_low_battery
        to: "on"
      - trigger: state
        entity_id: binary_sensor.aranet_1a2b3c_base_station
        to: "off"   # connectivity class: off means disconnected
    actions:
      - action: notify.mobile_app_phone
        data:
          message: "An Aranet device needs attention."
```

## Limitations

- **Cloud-only.** The integration talks to the Aranet Cloud REST API, not to
  sensors over Bluetooth. You need internet access and a cloud-synced base
  station. For local Bluetooth, use the built-in `aranet` integration.
- **Read-only.** Only `GET` endpoints are used, so you can't change sensor or
  account settings from Home Assistant.
- **Fixed 60-second cadence.** Sub-minute resolution isn't available, and the
  upstream sample rate wouldn't supply it.
- **Only two alarm rules.** User-defined Aranet alarm rules beyond low battery
  and base offline aren't surfaced as binary sensors yet.
- **Units follow your account preference.** Home Assistant's own unit
  conversion can override the display.
- **Branding needs HA 2026.3 or later.** The bundled icon and logo are served
  by Home Assistant's local Brands Proxy, which older cores don't have.

## Remove the integration

1. Go to **Settings > Devices & services**.
2. Click the **Aranet Cloud** entry.
3. Select **⋮ > Delete**.

Deleting the config entry removes every device and entity the integration
created and discards the stored API key. To remove the code as well, open
**HACS > Aranet Cloud > ⋮ > Remove**, or delete
`custom_components/aranet_cloud/` for a manual install, then restart Home
Assistant. Your Aranet Cloud account is untouched.

## Troubleshoot

### "Could not connect to Aranet Cloud" during setup

- Check your internet connection.
- Confirm `https://aranet.cloud/api/v1/sensors` is reachable from the Home
  Assistant host. Try `curl -H "ApiKey: yours" …`.
- The API sits behind Cloudflare, and some corporate networks block
  Cloudflare-fronted endpoints.

### "The API key was rejected"

- Check that you copied the whole key with no trailing whitespace.
- Confirm the key wasn't revoked in the Aranet Cloud dashboard.
- If you rotated the key recently, Home Assistant shows a reauthentication
  prompt under **Settings > Devices & services** where you can paste the new
  one.

### Every entity shows `unavailable`

- Check the integration tile for setup errors.
- Select **Download diagnostics** and look at `coordinator.last_update_success`
  and the raw snapshot. The API key is redacted.

### One entity is `unavailable` while its siblings are fine

That entity's most recent reading is more than 20 minutes old, which usually
means a flat battery or a sensor out of range of its base. The coordinator is
still polling successfully and the tile shows no error, which is why the rest
of the fleet looks healthy.

Enable the sensor's **Signal strength** entity, a diagnostic that's disabled by
default, to watch for a weak signal.

### Turn on debug logging

Use the integration page and select **⋮ > Enable debug logging**, which covers
the `aranet-cloud` client library as well. To do it in YAML instead, add the
following to `configuration.yaml` and restart:

```yaml
logger:
  logs:
    custom_components.aranet_cloud: debug
    aranet_cloud: debug   # the underlying REST client library
```

At `debug`, **Settings > System > Logs** shows:

- **Setup.** The entry name, sensor and base counts, and poll interval.
- **Each poll.** One `Polled Aranet Cloud: N sensor(s), N base(s), …` line per
  cycle, so you can confirm data is flowing and how much.
- **Entity changes.** `Adding N sensor entit…: <unique_id>, …` whenever a new
  sensor or metric appears.
- **Unrendered metrics.** `Sensor X reports metric id N … skipping`, once per
  sensor and metric, if Aranet reports something the integration doesn't render
  yet. That's worth an issue, since adding it is a one-row change.
- **Retries and timeouts** from the client library.

Device cleanup logs a single line at `INFO`, so you'll see it without turning
on debug.

The API key never appears in the log at any level. Coordinator failures are
logged once when they start and once when they recover, which is standard Home
Assistant behavior, so a flaky connection won't flood the log.

## Report an issue

Use the [issue tracker](https://github.com/jasonjhofmann/aranet-cloud-homeassistant/issues).
Attach the diagnostics download. The API key is redacted before the snapshot is
generated, so it's safe to share.

For intermittent problems, turn on debug logging first and include the log.

## How the integration is built

- **A standalone client library.**
  [`aranet-cloud`](https://github.com/jasonjhofmann/aranet-cloud) is an async
  Python wrapper for the Aranet Cloud REST API covering 25 of its 27 GET
  endpoints. It's usable outside Home Assistant.
- **One coordinator.** A single `DataUpdateCoordinator` fetches measurements,
  telemetry, and alarms each cycle, refreshing the base and sensor catalogs in
  the same pass.
- **Base devices registered first.** Base stations are registered before sensor
  entities so the `via_device` hierarchy link resolves correctly under the
  HA 2025.12 and later rules.
- **Bundled brand assets.** The icon and logo live in
  `custom_components/aranet_cloud/brand/` and are served by Home Assistant's
  Brands Proxy API, so no pull request to `home-assistant/brands` is needed.

The integration is at the Platinum tier of the Home Assistant Integration
Quality Scale. See
[`custom_components/aranet_cloud/quality_scale.yaml`](custom_components/aranet_cloud/quality_scale.yaml)
for per-rule status.

## License

Apache 2.0. See [LICENSE](LICENSE).

Aranet branding is bundled at `custom_components/aranet_cloud/brand/` and
served through Home Assistant's Brands Proxy API. "Aranet" is a trademark of
SAF Tehnika.

## Related projects

- [visiblair-homeassistant](https://github.com/jasonjhofmann/visiblair-homeassistant)
  reads VisiblAir air-quality sensors into Home Assistant.
- [sensoredlife-homeassistant](https://github.com/jasonjhofmann/sensoredlife-homeassistant)
  reads SensoredLife MarCELL cellular monitors into Home Assistant.
