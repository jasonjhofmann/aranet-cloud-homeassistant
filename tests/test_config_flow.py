"""Config + reauth flow tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from aranet_cloud import AranetAuthError, AranetError
from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.aranet_cloud.config_flow import _account_id
from custom_components.aranet_cloud.const import DOMAIN

from .conftest import TEST_API_KEY, patch_clients


async def _start_user_flow(hass: HomeAssistant) -> str:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    return result["flow_id"]


async def test_user_flow_success(
    hass: HomeAssistant, patch_config_flow_client: MagicMock
) -> None:
    """Happy path: a valid key creates an entry titled after the single base."""
    flow_id = await _start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_API_KEY: f"  {TEST_API_KEY}  "}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Aranet-1a2b3c"
    assert result["data"] == {CONF_API_KEY: TEST_API_KEY}  # whitespace stripped


async def test_user_flow_title_multiple_bases(
    hass: HomeAssistant, patch_config_flow_client: MagicMock
) -> None:
    """With >1 base the title falls back to a sensor count."""
    from . import fixtures_data as data

    patch_config_flow_client.get_bases.return_value = [
        data.build_base(base_id="1", name="Base A"),
        data.build_base(base_id="2", name="Base B"),
    ]
    flow_id = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_API_KEY: TEST_API_KEY}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Aranet Cloud (2 sensors)"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (AranetAuthError("bad key"), "invalid_auth"),
        (AranetError("boom"), "cannot_connect"),
    ],
)
async def test_user_flow_errors_then_recovers(
    hass: HomeAssistant,
    patch_config_flow_client: MagicMock,
    error: Exception,
    expected: str,
) -> None:
    """Validation failures surface as form errors; a later good key recovers."""
    patch_config_flow_client.get_sensors.side_effect = error
    flow_id = await _start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_API_KEY: TEST_API_KEY}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}

    # Clear the fault and retry within the same flow.
    patch_config_flow_client.get_sensors.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: TEST_API_KEY}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_aborts_on_duplicate(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    patch_config_flow_client: MagicMock,
) -> None:
    """A second setup of the same account aborts as already_configured."""
    mock_config_entry.add_to_hass(hass)

    flow_id = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_API_KEY: TEST_API_KEY}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    patch_config_flow_client: MagicMock,
) -> None:
    """Reauth updates the stored key and reloads the entry."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "fresh-rotated-key"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "fresh-rotated-key"


async def test_reconfigure_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Reconfigure validates and swaps in the new key, then reloads."""
    mock_config_entry.add_to_hass(hass)

    with patch_clients(mock_client):
        result = await mock_config_entry.start_reconfigure_flow(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reconfigure"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "rotated-key"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "rotated-key"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (AranetAuthError("bad key"), "invalid_auth"),
        (AranetError("boom"), "cannot_connect"),
    ],
)
async def test_reconfigure_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    error: Exception,
    expected: str,
) -> None:
    """A failed reconfigure re-shows the form and leaves the key unchanged."""
    mock_config_entry.add_to_hass(hass)
    mock_client.get_sensors.side_effect = error

    with patch_clients(mock_client):
        result = await mock_config_entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "rotated-key"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}
    assert mock_config_entry.data[CONF_API_KEY] == TEST_API_KEY


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (AranetAuthError("bad key"), "invalid_auth"),
        (AranetError("boom"), "cannot_connect"),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    patch_config_flow_client: MagicMock,
    error: Exception,
    expected: str,
) -> None:
    """A failed reauth re-shows the form with the right error."""
    mock_config_entry.add_to_hass(hass)
    patch_config_flow_client.get_sensors.side_effect = error

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "another-key"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}
    # Original key unchanged after a failed reauth.
    assert mock_config_entry.data[CONF_API_KEY] == TEST_API_KEY


async def test_reauth_rotates_unique_id_so_duplicate_add_aborts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    patch_config_flow_client: MagicMock,
) -> None:
    """After key rotation via reauth, re-adding the account still dedupes.

    Regression: reauth used to update only ``data`` — the entry kept the OLD
    key's hash as unique_id, so adding the same account with the new key
    created a duplicate entry with colliding devices.
    """
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "fresh-rotated-key"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.unique_id == _account_id("fresh-rotated-key")

    # A new user flow with the rotated key must abort as already_configured.
    flow_id = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_API_KEY: "fresh-rotated-key"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_rotates_unique_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Reconfigure keeps the unique_id in step with the new key's hash."""
    mock_config_entry.add_to_hass(hass)

    with patch_clients(mock_client):
        result = await mock_config_entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "rotated-key"}
        )
        await hass.async_block_till_done()

    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.unique_id == _account_id("rotated-key")
