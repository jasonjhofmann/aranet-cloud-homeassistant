"""Diagnostics tests — redaction of the key/unique_id and snapshot shape."""

from __future__ import annotations

import json

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.aranet_cloud.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .conftest import TEST_API_KEY


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

    # The raw key must not survive anywhere in the serialised payload.
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
        "apiKey": "abc",
        "nested": {"location": "Kitchen"},
        "name": "Aranet4 0ABCD",  # non-sensitive keys survive
    }
    out = async_redact_data(hypothetical_raw, REDACT)
    for key in ("location", "region", "note", "notes", "Authorization", "apiKey"):
        assert out[key] == "**REDACTED**"
    assert out["nested"]["location"] == "**REDACTED**"
    assert out["name"] == "Aranet4 0ABCD"
