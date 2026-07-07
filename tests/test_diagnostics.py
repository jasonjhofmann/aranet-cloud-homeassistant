"""Diagnostics tests — redaction of the key/unique_id and snapshot shape."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.aranet_cloud.diagnostics import (
    async_get_config_entry_diagnostics,
)

from . import fixtures_data as data
from .conftest import (
    TEST_API_KEY,
    build_mock_client,
    patch_clients,
    setup_integration,
)


async def test_diagnostics_redacts_and_counts(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The key + unique_id are redacted and the counts match the fixture fleet."""
    result = await async_get_config_entry_diagnostics(hass, init_integration)

    assert result["config_entry"]["data"][CONF_API_KEY] == "**REDACTED**"
    assert result["config_entry"]["unique_id"] == "**REDACTED**"
    # A loaded entry reports its state, and a base's region is redacted (it is
    # present in every dump via Base.region, not merely a hypothetical key).
    assert result["config_entry"]["state"] == "loaded"
    assert result["bases"][0]["region"] == "**REDACTED**"

    assert result["counts"] == {
        "sensors": 2,
        "bases": 1,
        "readings": 12,  # 8 gauge + 4 telemetry
        "active_alarms": 0,
    }
    assert len(result["sensors"]) == 2
    assert len(result["bases"]) == 1

    # Healthy poll: success flag set, no captured exception.
    assert result["coordinator"]["last_update_success"] is True
    assert result["coordinator"]["last_exception"] is None

    # A wall-clock reference so the readings' own timestamps are interpretable.
    assert result["generated_at"] == data.FIXED_TIME.isoformat()

    # The raw key must not survive anywhere in the serialised payload.
    assert TEST_API_KEY not in json.dumps(result)


async def test_diagnostics_captures_failure_cause(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """After a failed refresh, the dump surfaces the chained failure cause.

    The coordinator raises a translated UpdateFailed whose str() is empty; the
    dump must still show the real reason (its __cause__) so a maintainer can
    diagnose from the download alone.
    """
    from aranet_cloud import AranetError

    coordinator = init_integration.runtime_data
    mock_client.get_measurements_last.side_effect = AranetError("503 upstream")
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    result = await async_get_config_entry_diagnostics(hass, init_integration)

    assert result["coordinator"]["last_update_success"] is False
    assert "503 upstream" in result["coordinator"]["last_exception"]


async def test_diagnostics_omits_stale_exception_after_recovery(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """A recovered coordinator must not present its last failure as current.

    HA's coordinator retains ``last_exception`` after a successful poll; the
    dump must not surface it once ``last_update_success`` is True again, or a
    maintainer chases an already-resolved error.
    """
    from aranet_cloud import AranetError

    coordinator = init_integration.runtime_data

    # Fail one refresh...
    mock_client.get_measurements_last.side_effect = AranetError("transient 503")
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.last_update_success is False

    # ...then recover.
    mock_client.get_measurements_last.side_effect = None
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.last_update_success is True

    result = await async_get_config_entry_diagnostics(hass, init_integration)

    assert result["coordinator"]["last_update_success"] is True
    assert result["coordinator"]["last_exception"] is None


async def test_diagnostics_scrubs_api_key_from_exception(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """A key echoed into an error message is scrubbed from the failure string.

    ``async_redact_data`` only masks sensitive dict *keys*; it cannot reach a
    secret embedded in the free-text ``last_exception``. A future library that
    put the key in a URL/header/body of an error must still not leak it into a
    dump users paste into public issues.
    """
    from aranet_cloud import AranetError

    coordinator = init_integration.runtime_data
    mock_client.get_measurements_last.side_effect = AranetError(
        f"401 rejected key={TEST_API_KEY}"
    )
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    result = await async_get_config_entry_diagnostics(hass, init_integration)

    last_exception = result["coordinator"]["last_exception"]
    assert result["coordinator"]["last_update_success"] is False
    # The failure is still described (context preserved)...
    assert "401 rejected" in last_exception
    # ...but the raw key is scrubbed, both in the field and the whole dump.
    assert "**REDACTED**" in last_exception
    assert TEST_API_KEY not in json.dumps(result)


async def test_diagnostics_partial_dump_when_first_refresh_failed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """An entry stuck in SETUP_RETRY still yields a redacted partial dump.

    The first refresh never completed, so ``runtime_data`` is unset and there
    is no snapshot — but downloading diagnostics (which the README funnels
    users to for exactly this failure) must not crash.
    """
    from aranet_cloud import AranetError

    client = build_mock_client()
    client.get_sensors.side_effect = AranetError("cloud 503")
    mock_config_entry.add_to_hass(hass)
    with patch_clients(client):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert getattr(mock_config_entry, "runtime_data", None) is None

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    # Redaction survives on the partial path, and the failure is describable.
    assert result["config_entry"]["data"][CONF_API_KEY] == "**REDACTED**"
    assert result["config_entry"]["unique_id"] == "**REDACTED**"
    assert result["config_entry"]["state"] == "setup_retry"
    assert result["coordinator"] is None
    assert "note" in result
    assert "generated_at" in result
    # No snapshot-derived sections when there is no snapshot.
    assert "counts" not in result
    assert "sensors" not in result
    assert TEST_API_KEY not in json.dumps(result)


async def test_diagnostics_partial_dump_when_snapshot_missing(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A coordinator that exists but holds no snapshot yields a partial dump.

    Guards the `runtime_data set, coordinator.data is None` window without
    raising, still reporting coordinator status.
    """
    coordinator = init_integration.runtime_data
    coordinator.data = None  # simulate the pre-first-snapshot window

    result = await async_get_config_entry_diagnostics(hass, init_integration)

    assert result["coordinator"]["name"] == coordinator.name
    assert result["coordinator"]["last_update_success"] is True
    assert result["coordinator"]["last_exception"] is None
    assert "note" in result
    assert "counts" not in result
    assert result["config_entry"]["data"][CONF_API_KEY] == "**REDACTED**"
    assert TEST_API_KEY not in json.dumps(result)


def test_redact_set_covers_raw_payload_keys() -> None:
    """Future-proofing: raw Aranet Cloud payload keys scrub even though
    today's dump never includes raw payloads (guards against drift)."""
    from homeassistant.components.diagnostics import async_redact_data

    from custom_components.aranet_cloud.diagnostics import REDACT

    hypothetical_raw = {
        "location": "Primary Bedroom",
        "region": "us-1",
        "note": "behind the headboard",
        "notes": ["spare key under mat"],
        "Authorization": "Bearer abc",
        # The live auth header is spelled "ApiKey" (README curl); the older
        # lowercase variant is kept too. Both must redact.
        "ApiKey": "abc",
        "apiKey": "abc",
        "nested": {"location": "Kitchen"},
        "name": "Aranet4 0ABCD",  # non-sensitive keys survive
    }
    out = async_redact_data(hypothetical_raw, REDACT)
    for key in (
        "location",
        "region",
        "note",
        "notes",
        "Authorization",
        "ApiKey",
        "apiKey",
    ):
        assert out[key] == "**REDACTED**"
    assert out["nested"]["location"] == "**REDACTED**"
    assert out["name"] == "Aranet4 0ABCD"


async def test_base_config_is_redacted(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Base.config (enterprise gateway configuration) never leaks into the dump."""
    base = data.build_base()
    base.config = {"wifi": {"ssid": "HomeNet", "psk": "hunter2"}}
    client = build_mock_client(bases=[base])
    await setup_integration(hass, mock_config_entry, client)

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert result["bases"][0]["config"] == "**REDACTED**"
    assert "hunter2" not in json.dumps(result)


def test_describe_exception_preserves_trailing_colon() -> None:
    """A legitimate message ending in ':' is not truncated (no rstrip strip)."""
    from custom_components.aranet_cloud.diagnostics import _describe_exception

    summary = _describe_exception(ValueError("expected JSON, got:"))
    assert summary == "ValueError: expected JSON, got:"


def test_describe_exception_collapses_empty_message() -> None:
    """An empty-message exception renders as just its type name."""
    from homeassistant.helpers.update_coordinator import UpdateFailed

    from custom_components.aranet_cloud.diagnostics import _describe_exception

    assert _describe_exception(UpdateFailed()) == "UpdateFailed"


def test_describe_exception_scrubs_secret_substring() -> None:
    """The known key value is scrubbed from the rendered summary."""
    from custom_components.aranet_cloud.diagnostics import _describe_exception

    summary = _describe_exception(ValueError("rejected key=SEKRET"), secret="SEKRET")
    assert summary is not None
    assert "SEKRET" not in summary
    assert "**REDACTED**" in summary
