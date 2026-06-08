"""Coordinator tests — exception translation keys for auth/update failures."""

from __future__ import annotations

import pytest
from aranet_cloud import AranetAuthError, AranetError
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.aranet_cloud.const import DOMAIN
from custom_components.aranet_cloud.coordinator import AranetCoordinator

from .conftest import build_mock_client


async def test_auth_error_is_translated(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A 401 raises ConfigEntryAuthFailed with a translation key, not a raw message."""
    mock_config_entry.add_to_hass(hass)
    client = build_mock_client()
    client.get_sensors.side_effect = AranetAuthError("nope")
    coordinator = AranetCoordinator(hass, mock_config_entry, client=client)

    with pytest.raises(ConfigEntryAuthFailed) as exc:
        await coordinator._async_update_data()

    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "auth_failed"


async def test_update_error_is_translated(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Other API errors raise UpdateFailed with a translation key + the detail."""
    mock_config_entry.add_to_hass(hass)
    client = build_mock_client()
    client.get_measurements_last.side_effect = AranetError("503 upstream")
    coordinator = AranetCoordinator(hass, mock_config_entry, client=client)

    with pytest.raises(UpdateFailed) as exc:
        await coordinator._async_update_data()

    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "update_failed"
    assert exc.value.translation_placeholders == {"error": "503 upstream"}
