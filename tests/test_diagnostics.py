"""Diagnostics tests — redaction of the key/unique_id and snapshot shape."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.aranet_cloud.diagnostics import (
    async_get_config_entry_diagnostics,
)

from . import fixtures_data as data
from .conftest import TEST_API_KEY, build_mock_client, setup_integration


async def test_diagnostics_redacts_and_counts(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The key + unique_id are redacted and the counts match the fixture fleet."""
    result = await async_get_config_entry_diagnostics(hass, init_integration)

    assert result["config_entry"]["data"][CONF_API_KEY] == "**REDACTED**"
    assert result["config_entry"]["unique_id"] == "**REDACTED**"

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
        "apiKey": "abc",
        "nested": {"location": "Kitchen"},
        "name": "Aranet4 0ABCD",  # non-sensitive keys survive
    }
    out = async_redact_data(hypothetical_raw, REDACT)
    for key in ("location", "region", "note", "notes", "Authorization", "apiKey"):
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
