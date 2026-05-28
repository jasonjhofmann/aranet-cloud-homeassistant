# Changelog

All notable changes to **aranet-cloud-homeassistant** are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning is [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing yet.

## [0.4.0] — 2026-05-27

### Removed (breaking)

- **OptionsFlow** and user-configurable poll interval. HA Core convention
  is that the integration owns its cadence; we now poll at a fixed 60 s
  (matching Aranet sensors' 60 s sample rate, which was the previous
  default). Old config entries with a saved `options.scan_interval` are
  tolerated — the value is simply ignored. `CONF_SCAN_INTERVAL`,
  `MIN_SCAN_INTERVAL_SECONDS`, and `MAX_SCAN_INTERVAL_SECONDS` dropped
  from `const.py`.

### Added

- **`quality_scale.yaml`** (Bronze tier) with Silver-tier rule status
  pre-mapped (done / todo / exempt).
- **`"quality_scale": "bronze"`** in `manifest.json`.
- **PEP-561 `py.typed`** marker so downstream type-checkers honour the
  integration's type hints.
- **`.github/copilot-instructions.md`** — HA Core integration conventions
  adapted for custom integrations, so AI assistants editing this repo
  produce idiomatic HA-style code.

### Changed

- HACS `homeassistant` floor bumped `2024.12.0` → `2025.1.0`.
- `AranetCoordinator.__init__` now takes the `ConfigEntry` directly and
  passes it to `super().__init__(config_entry=entry)` per the HA 2024.10+
  pattern (so HA can attribute coordinator errors).
- `_async_options_updated` listener removed (no options to react to).
- README updated to reflect the fixed cadence.

### Notes

Closes Bronze quality-scale blockers for HA Core acceptance. Remaining
gaps (deferred): no tests, no CI workflows, no `pyproject.toml`,
`async_step_reconfigure` not implemented (Silver-tier).

## [0.3.0] — 2026-05-19

Phase 3 — full feature coverage. From 6 entities to 77, all sensor types
and metrics supported.

### Added

- **Generic, table-driven sensor entity** (`AranetMetricSensor`) replacing
  the Phase 2 single-metric proof-of-concept. New metrics are now a
  one-row addition to `METRIC_REGISTRY`.
- Sensor entities for every supported metric: temperature, humidity, CO₂,
  atmospheric pressure, volumetric water content (soil moisture), soil
  dielectric permittivity, soil electrical conductivity, pore electrical
  conductivity, vapour-pressure deficit, day light integral, RSSI
  (diagnostic), battery (diagnostic).
- **Dynamic `native_unit_of_measurement`** — the unit is derived from
  the API response per reading, preserving the user's Aranet account
  preference (°F vs °C, mmHg vs hPa, etc.). HA's built-in unit conversion
  still applies on top.
- **Base station devices** with one diagnostic `Firmware` entity each.
  Sensor devices are linked via `via_device` to their primary base.
- **Binary-sensor platform** (`binary_sensor.py`):
  - `AranetLowBatteryBinarySensor` per battery-reporting sensor — on
    when Aranet's built-in *Low battery* alarm rule is firing.
  - `AranetBaseOfflineBinarySensor` per base station — uses HA's
    `connectivity` device class (on = connected).
- **Diagnostics platform** (`diagnostics.py`) — "Download diagnostics"
  produces a sanitised snapshot of the entire integration state with the
  API key and account hash redacted.
- **Options flow** for runtime tuning. Currently exposes scan interval
  (30–600 s, default 60 s); future runtime options will accumulate here.
- **Brand assets** bundled in `custom_components/aranet_cloud/brand/`
  via HA's new Brands Proxy API (HA 2026.3+). Icon, logo, and dark-mode
  variants ship with the integration — no separate PR to
  `home-assistant/brands` required.

### Changed

- Bumped to v0.3.0.
- `manifest.json` now declares `iot_class: cloud_polling` (was unset).
- Base devices are pre-registered in `async_setup_entry` before platforms
  are forwarded, so sensor entities can safely set `via_device` without
  triggering HA's 2025.12 deprecation warning.

### Fixed

- The `via_device` deprecation warning logged on first Phase 3 deploy
  ("calls `device_registry.async_get_or_create` referencing a non
  existing via_device").

## [0.1.0] — 2026-05-19

Phase 2 — minimum viable wiring. CO₂ entity per Aranet4 sensor, proving
the integration plumbs from config flow through coordinator to entity
state.

### Added

- Initial HACS integration scaffolding.
- `manifest.json`, `hacs.json`, English `strings.json` + translations.
- Config flow with API-key validation against `GET /api/v1/sensors`.
- Reauth flow stub on 401 responses.
- Salted SHA-256 hash as the config-entry `unique_id` so the raw API key
  never ends up in HA's registry as an identifier.
- `AranetCoordinator` (single `DataUpdateCoordinator`) polling
  measurements/last and telemetry/last.
- `AranetCO2Sensor` — one entity per CO₂-capable sensor.
- Aranet brand assets bundled in `brand/` (Phase 3 work, backported to
  the 0.1.x lineage for context).

[Unreleased]: https://github.com/jasonjhofmann/aranet-cloud-homeassistant/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/jasonjhofmann/aranet-cloud-homeassistant/releases/tag/v0.4.0
[0.3.0]: https://github.com/jasonjhofmann/aranet-cloud-homeassistant/releases/tag/v0.3.0
[0.1.0]: https://github.com/jasonjhofmann/aranet-cloud-homeassistant/releases/tag/v0.1.0
