# Contributing

Issues and pull requests welcome — this integration is community-built.

## Reporting a bug

Open an issue with:

1. **The version of the integration** (visible on the integration tile, or
   in `manifest.json`).
2. **Your HA Core + OS version** (Settings → About).
3. **A diagnostics download** from the integration tile. The API key is
   automatically redacted before the snapshot is built, so it's safe to
   paste verbatim.
4. **What you expected vs. what happened.** Include relevant log lines
   from Settings → System → Logs filtered to `custom_components.aranet_cloud`
   (or `aranet_cloud`).

## Suggesting a metric / sensor type

As of v0.7.0 the integration renders **every metric class in the current
Aranet Cloud catalog**. If Aranet adds a new one (or your account exposes a
metric that isn't appearing), open an issue with:

- The metric ID. Two easy ways to find it: enable debug logging (see the
  README's *Enabling debug logs*) and look for
  `Sensor … reports metric id N … — skipping`, or read it from a diagnostics
  download under `sensors[*].skills[*].metric`.
- The metric name and unit options (from `GET /api/v1/metrics` — feel free to
  paste the JSON response).
- What unit you expect HA to display.

Adding a metric is usually a one-row change to `METRIC_REGISTRY` in
`custom_components/aranet_cloud/sensor.py`, plus its unit IDs in
`UNIT_BY_ID` and an entity-name string. Set a `device_class` **only** when
every Aranet unit option for the metric is a valid Home Assistant unit for
that class; otherwise render it as a plain measurement sensor (as Distance,
Differential pressure, and Radon do).

## Development setup

This repo is the HA integration. The async REST client lives in a separate
repo: [`aranet-cloud`](https://github.com/jasonjhofmann/aranet-cloud).

```bash
# Clone both
git clone https://github.com/jasonjhofmann/aranet-cloud
git clone https://github.com/jasonjhofmann/aranet-cloud-homeassistant

# Develop against a local checkout of the client lib
cd aranet-cloud
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest

# To test against your live HA box:
python -m build --wheel
# Then transfer the wheel and pip install inside the homeassistant container:
#   docker exec homeassistant pip install /path/to/aranet_cloud-*.whl
# Copy custom_components/aranet_cloud/ to /config/custom_components/
# Restart HA.
```

See `../aranet-cloud/docs/architecture.md` for the API + library design,
and the integration's `coordinator.py` / `sensor.py` for the HA-side
patterns.

## Running the integration's checks

This repo has its own test suite and tooling config (`pyproject.toml`,
`requirements_test.txt`). The tests use
[`pytest-homeassistant-custom-component`](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component),
which pulls in a pinned Home Assistant.

```bash
cd aranet-cloud-homeassistant
python -m venv .venv && source .venv/bin/activate
pip install -r requirements_test.txt ruff mypy aranet-cloud

ruff check custom_components/ tests/        # lint
ruff format --check custom_components/ tests/
mypy custom_components/aranet_cloud/         # strict typing
pytest --cov=custom_components.aranet_cloud --cov-report=term-missing
```

The CI workflow (`.github/workflows/ci.yml`) runs the same checks and gates
coverage at **≥95%** (the suite currently sits at 100%). Test fixtures must
use **synthetic** device identifiers only — never paste real serials, base
IDs, or MACs.

> **Note on `mypy`.** The integration package is named `aranet_cloud`, the
> same as its dependency library. `pyproject.toml` anchors mypy at the repo
> root (`mypy_path`, `explicit_package_bases`) so `from aranet_cloud import …`
> resolves to the installed library, not the integration itself. Run mypy
> from the repo root.

## Code style

`ruff` + strict `mypy` are configured in `pyproject.toml` for this repo (and
the `aranet-cloud` client lib follows the same conventions). HA's core check
tools (`hassfest`, plus the `validate.yml` HACS action) must also pass.

## License

Contributions are accepted under the same Apache 2.0 license as the rest
of the project.
