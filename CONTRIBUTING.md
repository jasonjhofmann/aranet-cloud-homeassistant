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

If your account exposes a metric or sensor type the integration doesn't
yet handle, open an issue with:

- The metric ID (visible in your diagnostics download under `sensors[*].skills[*].metric`)
- The metric name (from `GET /api/v1/metrics/{id}` — feel free to paste
  the JSON response)
- What unit you expect HA to display

Adding a new metric is usually a one-row change to `METRIC_REGISTRY` in
`custom_components/aranet_cloud/sensor.py`.

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

## Code style

The Python client lib (`aranet-cloud`) ships with `ruff` + `mypy` strict
configuration. The integration code follows the same conventions; HA's
core check tools (`hassfest`, `homeassistant.const` linting via ruff)
should also pass.

## License

Contributions are accepted under the same Apache 2.0 license as the rest
of the project.
