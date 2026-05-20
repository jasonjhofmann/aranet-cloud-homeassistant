# Aranet Cloud

Async, read-only Home Assistant integration for the [Aranet Cloud](https://aranet.cloud/)
REST API. Brings every sensor in your Aranet Cloud account into Home
Assistant — including ones that aren't in Bluetooth range of the HA host.

## What it does

- Discovers every Aranet sensor + base station on your account
- Creates one HA device per sensor, parented to its base station
- Exposes every metric your sensors report (temperature, humidity, CO₂,
  atmospheric pressure, soil moisture, soil EC, pore EC, soil
  permittivity, vapour-pressure deficit, day light integral, RSSI,
  battery) as standard `sensor` entities
- Surfaces Aranet's built-in alarm rules (Low battery, Base station
  offline) as `binary_sensor` entities
- Adds a diagnostic firmware entity to each base station
- Provides an Options panel for tunable poll cadence (30–600 s)
- Provides a reauth flow if your API key is rotated or revoked
- Provides a Diagnostics download with credentials auto-redacted

## What it doesn't do

- **Write** anything to your Aranet account. The API used is read-only.
- Replace the built-in Bluetooth Aranet integration. The two can coexist
  — though most users will prefer this cloud-backed one because it
  covers sensors out of BLE range.

## Setup

You need an API key from your Aranet Cloud dashboard (Account → API).
Paste it into the integration setup form. The integration validates it
against the live API before saving.

## Supported sensor types

53 Aranet sensor types covered (whatever your account reports). Tested
end-to-end with Aranet4, Aranet2, Aranet legacy 2-metric, basic capacitive
soil moisture, and the WET150 multi-parameter soil probe.

## More information

- [README](README.md)
- [Changelog](CHANGELOG.md)
- [Repository](https://github.com/jasonjhofmann/aranet-cloud-homeassistant)
