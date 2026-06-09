# Changelog

All notable changes to **aranet-cloud-homeassistant** are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning is [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing yet.

## [0.7.0] — 2026-06-09

### Added

- **Complete metric coverage** — six metric classes from the Aranet Cloud
  catalog that were previously dropped now render as entities, so every
  catalog metric is supported:
  - **Voltage** (device class `voltage`) and **Weight** (device class
    `weight`) — all their units are valid Home Assistant units.
  - **Distance**, **Differential pressure**, **Radon**, and **Fraction** —
    rendered as plain measurement sensors (no device class). Distance carries
    a `mil` unit and differential pressure a `mmH₂O` unit that Home Assistant
    doesn't define, and radon/fraction have no HA device class; radon mirrors
    the built-in BLE `aranet` integration (`Bq/m³`, `MEASUREMENT`).
  - Ground truth sourced from the live `/api/metrics` + `/api/user/units`
    responses; the new unit IDs are mapped in `UNIT_BY_ID`.

### Logging

- The previously-silent "metric not rendered" path now logs once per
  sensor/metric at `debug` (`Sensor … reports metric id N … — skipping`), so a
  new Aranet metric is discoverable rather than invisible. Documented in the
  README *Enabling debug logs* and CONTRIBUTING sections.

### Fixed (docs)

- Corrected two **overclaims** in the hardware/metric docs (README + info.md):
  - The "tested" sensor-type list claimed Aranet2 (S4V5) and the 0–10 VDC /
    4–20 mA transmitter bridges (S5V1/S5V2), which were never tested on
    hardware. Split into **Verified on real hardware** (Aranet4 S4V1, Aranet
    legacy S1V16, soil S6V4, WET150 S6V1) vs. **Expected — not yet verified**
    (now a *device-type* caveat only — metric coverage is complete).
  - Documented the full metric set in a **Supported metrics** section and the
    Entity reference table; corrected the soil/pore EC unit (`mS/cm`).

## [0.6.0] — 2026-06-08

Quality scale **Gold → Platinum** (`manifest.json` `"quality_scale": "platinum"`),
plus a logging and documentation pass.

The three Platinum rules were already met and are now declared (no functional
change to entities or devices):

- **`async-dependency`** — the `aranet-cloud` library is fully async (aiohttp);
  the integration never offloads to the executor.
- **`inject-websession`** — Home Assistant's shared aiohttp session is passed
  into `AranetCloudClient(session=...)` (the library never closes it).
- **`strict-typing`** — the integration and the `aranet-cloud` dependency
  (PEP-561 `py.typed`) both pass `mypy --strict`; CI enforces it.

### Logging

- Level-appropriate, secret-safe logging across the lifecycle: `debug` for
  setup (entry name, sensor/base counts, poll interval), each poll (counts),
  and dynamic entity additions (with unique IDs); an `info` line when a stale
  device is pruned. The API key is never logged at any level. See
  *README → Troubleshooting → Enabling debug logs*.

### Documentation

- `info.md`: removed the stale "Options panel for tunable poll cadence" line
  (the OptionsFlow was dropped in 0.4.0); now documents the fixed 60 s
  cadence, dynamic/stale devices, and the reconfigure flow.
- `README.md`: added an **Enabling debug logs** section; corrected the
  "unavailable" tip (Signal strength is disabled by default).
- `CONTRIBUTING.md`: how to run the integration's own ruff / mypy / pytest
  checks, plus the mypy package-name-shadowing note.

## [0.5.0] — 2026-06-08

Quality scale **Bronze → Gold** (`manifest.json` `"quality_scale": "gold"`).

### Added

- **Dynamic devices** — sensors that appear in the account after setup gain
  entities on the next poll, and removed sensors/bases have their devices
  pruned automatically (**stale devices**).
- **Reconfigure flow** — update the API key from the integration entry's
  **⋮ → Reconfigure** action, without removing and re-adding it.
- **Translated exceptions** — coordinator auth/update failures raise with
  `translation_key`s (`strings.json` `exceptions`).
- **Icon translations** (`icons.json`) for the soil, day-light-integral, and
  base-firmware entities; device-class entities use Home Assistant defaults.
- **Full pytest test suite** under `tests/` (config / reauth / reconfigure
  flows, setup/unload, coordinator auth + API-error paths, sensor and
  binary-sensor platforms, dynamic/stale devices, diagnostics redaction) at
  100% line coverage.
- **CI** (`.github/workflows/ci.yml`): ruff lint + format, strict `mypy`,
  pytest with a ≥95% coverage gate. **HACS + hassfest** validation workflow.
- **`pyproject.toml`** (ruff / mypy / pytest) and `requirements_test.txt`.
  The mypy config anchors the package at the repo root so the integration's
  own `aranet_cloud` package name doesn't shadow the dependency library.

### Changed

- **Signal-strength (RSSI)** sensor is now **disabled by default** (niche
  diagnostic). Enable it per entity if you want it.
- `PARALLEL_UPDATES = 0` declared on both platforms.
- Entity icons moved from code into `icons.json`.

### Fixed (docs)

- README **"Configuration"** no longer describes a polling-interval options
  flow (removed in 0.4.0); added **Use cases**, **Example automations**,
  **How data is updated**, **Known limitations**, and **Removing the
  integration** sections.
- README **License/branding** now states brand assets are bundled in-repo and
  served by HA's Brands Proxy (no `home-assistant/brands` PR — that repo no
  longer accepts custom-integration submissions).

### Internal

- Removed the dead `options` / `scan_interval` translation blocks left over
  from the 0.4.0 OptionsFlow removal.

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
