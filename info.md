# Aranet Cloud

Async, read-only Home Assistant integration for the [Aranet Cloud](https://aranet.cloud/)
REST API. Brings every sensor in your Aranet Cloud account into Home
Assistant — including ones that aren't in Bluetooth range of the HA host.

## What it does

- Discovers every Aranet sensor + base station on your account
- Creates one HA device per sensor, parented to its base station
- Exposes every metric class in the Aranet Cloud catalog as standard `sensor`
  entities — temperature, humidity, CO₂, atmospheric pressure, soil moisture,
  soil/pore EC, soil permittivity, vapour-pressure deficit, day light integral,
  voltage, weight, distance, differential pressure, radon, fraction, RSSI, and
  battery
- Surfaces Aranet's built-in alarm rules (Low battery, Base station
  offline) as `binary_sensor` entities
- Adds a diagnostic firmware entity to each base station
- Polls on a fixed 60-second cadence (matching Aranet's own sample rate)
- Adds entities for sensors that appear later, and removes devices the
  account stops reporting — automatically
- Provides reauth (key rotated/revoked) and reconfigure (change the key)
  flows, plus a Diagnostics download with credentials auto-redacted
- Platinum quality scale: fully async, strict-typed, 100% test coverage

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

The integration is catalog-driven — any sensor on your account appears, as
long as it reports one of the supported metrics (above). **Verified on real
hardware:** Aranet4 (S4V1), Aranet legacy 2-metric (S1V16), capacitive soil
moisture (S6V4), and the WET150 multi-parameter soil probe (S6V1). The other
~53 catalog types (e.g. Aranet2, the 0–10 VDC / 4–20 mA transmitter bridges)
should work but haven't been tested on hardware yet.

## More information

- [README](README.md)
- [Changelog](CHANGELOG.md)
- [Repository](https://github.com/jasonjhofmann/aranet-cloud-homeassistant)
