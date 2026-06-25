# Changelog

All notable changes to **aranet-cloud-homeassistant** are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning is [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.8.6 — 2026-06-25

Polish and robustness from a full-repo review. No change for the common case;
all entity/device contracts are unchanged.

### Fixed

- **Display precision now adapts to account-preference units.** A battery
  reported in volts (or atmospheric pressure in atm/bar) no longer rounds to a
  useless integer (3.7 V → "4 V", 0.97 atm → "1.0"): a per-unit precision floor
  mirrors the existing dynamic device-class/unit handling. `native_value` and
  long-term statistics are unaffected.
- **Reauth connection failures are now logged** like the initial-setup and
  reconfigure flows — previously a `cannot_connect` during reauth left no trail.
- Day-light-integral unit id 142 renders as `mol/m²/d` (was the ASCII
  `mol/m2/d`), so the same physical unit canonicalises to one string.
- Base-station `DeviceInfo` is defined once and reused by both the device
  registration and the entities, so the two can't drift.

### Added

- Diagnostics now include the coordinator's **last-update success flag and the
  last failure's cause** (the chained exception behind the translated
  `UpdateFailed`), so a failing poll can be diagnosed from the download alone.
  The API key is never included.
- The "unmodelled metric — skipping" notice is logged at **INFO** (still deduped,
  once per sensor × metric) so the documented "open an issue" cue is visible
  without enabling debug logging.

### Changed

- The test client is now `create_autospec`'d against the real `aranet-cloud`
  class, so a renamed/removed library method fails the suite instead of passing
  green and only breaking in production. New tests pin the `via_device` device
  hierarchy, the volts display-precision floor, and the diagnostics
  failure-cause field (67 tests, **100% coverage**).
- CI `astral-sh/setup-uv` bumped `v3` → `v6` (off the aging Node-20 runtime).
- Removed the unused `BUILTIN_ALARM_METRICS` constant.

### Docs

- README "What you get" now lists all 18 rendered metrics (was missing voltage,
  weight, distance, differential pressure, radon, fraction); added a Known
  Limitations note that bundled brand icons require HA 2026.3+ while the
  integration runs on HA 2025.1+; corrected the backing-library endpoint count
  to 25 of 27. Fixed stale `copilot-instructions` claims (current-only readings;
  Python 3.12+ floor) and several source comments ("salt" → static
  domain-separation prefix; dropped the internal "Phase 0/3" provenance;
  diagnostics "scan interval" → "poll interval"; "skill" → "metric").

## 0.8.5 — 2026-06-25

Dependency bump: **aranet-cloud 0.2.1 → 0.2.2**.

- **Library robustness/security hardening, transparent to the integration.**
  aranet-cloud 0.2.2 clamps a server-supplied `Retry-After` to the 30 s
  backoff cap — closing a path where a large value (e.g. a Cloudflare 429)
  made the client `await` for hours and silently wedged this integration's
  `DataUpdateCoordinator` poll. It also coerces malformed integer/float fields
  defensively (no bare `ValueError`/`TypeError` escaping `AranetError`),
  guards the 400 error-body parse against a non-object `error[]` item,
  converts timezone-aware datetimes to UTC before sending `from`/`to`, and
  sets `allow_redirects=False` on JSON requests so a server redirect cannot
  re-send the `ApiKey` to a foreign origin. Every surfaced failure remains an
  `AranetError` subclass, which the coordinator already maps to `UpdateFailed`
  (and the config flow to *cannot connect*) — no integration-side changes
  required.
- CI dependency pins updated to `aranet-cloud==0.2.2`.

## 0.8.4 — 2026-06-18

Test-coverage and CI hygiene from an audit follow-up. **No change to the
integration's runtime behavior** — the shipped `custom_components/` code is
unchanged apart from this version bump.

- **Coordinator success path is now directly tested.** New tests exercise
  `_async_update_data`'s snapshot construction, which the platform tests only
  reached incidentally: catalog id-indexing, the `id_by_serial` map, the
  `measurements ⊕ telemetry` readings union (including telemetry as
  last-writer on a metric-key collision), the multi-alarm highest-severity
  tie-break, and the empty-fleet build. Previously only the two
  error-translation paths were covered.
- **Stale-device prune now asserts the side effect.** A test confirms that
  pruning a stale device also removes its entities from the registry — the
  3-cycle hysteresis *decision* was already tested; the
  `remove_config_entry_id` effect was not.
- **Unknown-unit fallback is tested.** A reading whose unit id isn't in
  `UNIT_BY_ID` renders the value with no unit label and no device class
  (the README "unrecognised unit" contract).
- **CI:** removed the auto-`/code-review` workflow that ran on every PR
  (unintended; no-ops on fork PRs since GitHub withholds secrets there, and
  redundant with the on-demand `@claude` workflow). Bumped the remaining
  Claude workflow's `actions/checkout` to `v5` to match the other workflows.

## 0.8.3 — 2026-06-10

Dependency bump: **aranet-cloud 0.2.0 → 0.2.1**.

- **Library error-contract hardening, transparent to the integration.**
  aranet-cloud 0.2.1 wraps binary-download timeouts in
  `AranetConnectionError` (no more raw `TimeoutError` escaping the
  hierarchy), rejects non-object 200 JSON bodies with
  `AranetServerError`, and populates `AranetRateLimitError.retry_after`
  from the `Retry-After` header. All three are `AranetError` subclasses,
  which the coordinator already maps to `UpdateFailed` (and the config
  flow to *cannot connect*) — no integration-side changes required; the
  hardened paths simply can no longer crash outside that mapping.
- CI dependency pins updated to `aranet-cloud==0.2.1`.

## 0.8.2 — 2026-06-10

Adjacent-issue sweep from a follow-up audit.

- **API-key rotation can no longer collide two config entries.** Reauth
  and reconfigure now abort (*already configured*) when the new key's
  account hash is already owned by a *different* entry (same account
  configured twice, then one rotated onto the other's key). Previously
  both entries ended up with the same `unique_id` and colliding
  `(domain, serial)` devices.
- **Re-activated metrics no longer log duplicate-add registry errors.**
  When a metric's skill flipped inactive, the platforms dropped its key
  from their bookkeeping while the entity object remained — re-activation
  then re-added the same unique_id, logging "ID … already exists" on
  every occurrence. Keys are now tracked for the lifetime of the entity
  object and released only when the entity is actually removed (e.g.
  stale-device prune), on both the sensor and binary_sensor platforms.
- **Base-bound entities now go stale like metric sensors.** The base
  firmware sensor goes unavailable when `Base.last_seen` exceeds the same
  20-minute staleness window the metric sensors got in 0.8.0, and the
  low-battery binary sensor mirrors its underlying battery reading's
  staleness. The base-offline *connectivity* binary sensor is
  deliberately **not** gated on `last_seen`: a stale check-in is exactly
  the condition it reports — the cloud-side alarm keeps asserting
  *Disconnected* while the base is dark, and going unavailable would mask
  it.
- **Docs:** README status line no longer says "0.6.x"; CHANGELOG
  normalized — intro moved to the top, the *Unreleased* tooling items
  folded into 0.8.0 (where they actually shipped), header style unified.

## 0.8.1 — 2026-06-10

Dependency bump: **aranet-cloud 0.1.0 → 0.2.0**.

- **Null readings now surface as *unknown*, not `0.0`.** Since
  aranet-cloud 0.2.0, `Reading.value` is `float | None` — a `null` (or
  unparseable) value from the cloud is no longer coerced to `0.0`. The
  sensor entity passes `None` through, so Home Assistant shows *unknown*
  instead of a fabricated zero (which would have poisoned long-term
  statistics). `Alarm.value`/`worst` got the same treatment in the
  library; the integration's alarm logic only checks alarm presence, so
  no behavior change there — regression-tested anyway.
- **Request timeout now applies with injected sessions** (library fix,
  transparent to the integration — HA injects its shared session).
- CI dependency pins updated to `aranet-cloud==0.2.0`.

## 0.8.0 — 2026-06-10

Hardening release from a code audit.

- **Stale-device pruning got hysteresis.** A device is now removed only
  after it has been absent from **3 consecutive** successful refreshes,
  and an empty snapshot (no sensors and no bases — how a cloud hiccup can
  present) never prunes at all. Previously a single empty-but-successful
  response deleted every device and its entity-registry entries.
- **API-key rotation keeps duplicate-account protection.** Reauth and
  reconfigure now update the entry's `unique_id` (the salted key hash)
  alongside the key. Previously the entry kept the old key's hash, so
  re-adding the account with the rotated key created a duplicate entry
  with colliding devices.
- **Entities now resolve readings via the permanent serial.** The
  cloud-numeric sensor id is looked up from the snapshot on every update
  instead of being bound at entity construction — a sensor deleted and
  re-added in the cloud (new numeric id, same serial) keeps reporting.
- **Device classes are validated against the delivered unit.** Account
  display preferences can deliver units HA's device classes don't accept
  (`%RH` for humidity, `atm` for atmospheric pressure, `V` for battery,
  `dBW` for signal strength, fractions for moisture). Invalid combos now
  degrade gracefully: a better-fitting class where one exists (battery
  voltage in `V`/`mV` → `voltage`), otherwise no device class — instead
  of per-entity errors and broken long-term statistics. Exhaustively
  tested across every unit id in `UNIT_BY_ID`.
- **Entities go unavailable when their reading goes stale.** A reading
  older than 20 minutes (2× the coarsest 10-minute transmit interval the
  hardware offers) marks the entity unavailable — a dead sensor no longer
  reports its last value as live forever.
- **Diagnostics redact `Base.config`** (enterprise gateway configuration).
- **Removed the false "stored encrypted" claim** from the API-key help
  text — Home Assistant stores config-entry data as plain JSON in
  `.storage`. The accurate half (the key is never written back to your
  Aranet Cloud account) remains.
- Tooling/CI (no integration changes): Ruff `target-version` lowered from
  `py314` to `py312` — the oldest interpreter implied by the declared HA
  minimum (hacs.json `homeassistant: 2025.1.0` ran Python 3.12). Under
  `py314`, `ruff format` rewrites `except (A, B):` into the 3.14-only
  unparenthesized form (PEP 758) — the SyntaxError regression that
  shipped in visiblair-homeassistant 0.6.2. Mypy stays on 3.14 because it
  parses the installed current Home Assistant source.
- CI restructured: `lint` (ruff + mypy on Python 3.14), `syntax-floor`
  (`compileall` on Python 3.12), and `test` (pytest matrix on 3.13 and
  3.14; coverage gate unchanged).

## 0.7.2 — 2026-06-10

- Diagnostics redact set now pre-lists sensitive keys from Aranet
  Cloud's raw API payloads (location/region/notes) and request context
  (Authorization/apiKey) that the dump never includes today — if a
  future revision attaches raw data, they scrub automatically.
  Regression-tested.

## 0.7.1 — 2026-06-10

Observability gap-fill (no functional changes).

- `loggers: ["aranet_cloud"]` in the manifest — the integration page's
  **Enable debug logging** toggle now captures the client library's
  retry/timeout logging too.
- Debug-logging instructions in README (Reporting issues).
- `data_description` help text on the reauth and reconfigure key fields.
- CI/tooling moved to Python 3.14 (latest Home Assistant test harness
  requires it; pinning 3.13 silently tested against months-old HA).

## 0.7.0 — 2026-06-09

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

## 0.6.0 — 2026-06-08

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

## 0.5.0 — 2026-06-08

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

## 0.4.0 — 2026-05-27

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

## 0.3.0 — 2026-05-19

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

## 0.1.0 — 2026-05-19

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
