"""Shared fixtures for the Aranet Cloud test suite."""

from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aranet_cloud import Links
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.aranet_cloud.config_flow import _account_id
from custom_components.aranet_cloud.const import DOMAIN

from . import fixtures_data as data

TEST_API_KEY = "test-api-key-0123456789abcdef"


def state_for(hass: HomeAssistant, platform: str, unique_id: str) -> State | None:
    """Resolve a state by the entity's ``(platform, DOMAIN, unique_id)``."""
    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id(platform, DOMAIN, unique_id)
    assert entity_id, f"no entity registered for unique_id {unique_id!r}"
    return hass.states.get(entity_id)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> None:
    """Make HA load the integration from ``custom_components/`` in every test."""


def build_mock_client(
    *,
    sensors: list | None = None,
    bases: list | None = None,
    measurements: list | None = None,
    telemetry: list | None = None,
    alarms: list | None = None,
) -> MagicMock:
    """A MagicMock standing in for ``AranetCloudClient`` with async methods."""
    client = MagicMock()
    client.get_sensors = AsyncMock(
        return_value=data.build_sensors() if sensors is None else sensors
    )
    client.get_bases = AsyncMock(
        return_value=[data.build_base()] if bases is None else bases
    )
    client.get_measurements_last = AsyncMock(
        return_value=(
            data.build_measurement_readings() if measurements is None else measurements,
            Links(),
        )
    )
    client.get_telemetry_last = AsyncMock(
        return_value=(
            data.build_telemetry_readings() if telemetry is None else telemetry,
            Links(),
        )
    )
    client.get_alarms_actual = AsyncMock(return_value=[] if alarms is None else alarms)
    return client


@pytest.fixture
def mock_client() -> MagicMock:
    """A healthy default client: full fleet, fresh readings, no active alarms."""
    return build_mock_client()


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """A config entry whose unique_id matches the test key's salted hash."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Aranet-1a2b3c",
        data={CONF_API_KEY: TEST_API_KEY},
        unique_id=_account_id(TEST_API_KEY),
    )


@contextmanager
def patch_clients(client: MagicMock) -> Iterator[MagicMock]:
    """Patch ``AranetCloudClient`` in both the entry-setup and config-flow paths."""
    with (
        patch(
            "custom_components.aranet_cloud.AranetCloudClient",
            return_value=client,
        ),
        patch(
            "custom_components.aranet_cloud.config_flow.AranetCloudClient",
            return_value=client,
        ),
    ):
        yield client


async def setup_integration(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    client: MagicMock,
) -> None:
    """Add the entry and run setup with the client patched in both call sites."""
    entry.add_to_hass(hass)
    with patch_clients(client):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> MockConfigEntry:
    """Set up the integration with the healthy default client and return the entry."""
    await setup_integration(hass, mock_config_entry, mock_client)
    return mock_config_entry


@pytest.fixture
def patch_config_flow_client(
    mock_client: MagicMock,
) -> Generator[MagicMock]:
    """Patch the client used by the config flow; yields the mock for tweaking."""
    with patch(
        "custom_components.aranet_cloud.config_flow.AranetCloudClient",
        return_value=mock_client,
    ):
        yield mock_client
