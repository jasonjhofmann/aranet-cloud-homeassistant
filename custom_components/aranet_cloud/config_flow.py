"""Config + options flows.

Two flows live here:

* :class:`AranetCloudConfigFlow` — initial setup + reauth. User pastes an
  API key; we validate it by calling ``get_sensors()`` and ``get_bases()``,
  then create one entry per account (deduplicated via a salted-hash
  ``unique_id`` so the raw key never lands in HA's registry).
* :class:`AranetCloudOptionsFlow` — runtime tunables. Currently just the
  poll interval; future-proofed via a single form-step pattern.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from aranet_cloud import AranetAuthError, AranetCloudClient, AranetError
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
    MAX_SCAN_INTERVAL_SECONDS,
    MIN_SCAN_INTERVAL_SECONDS,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})


class AranetCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Initial setup + reauth."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self,
        user_input: Mapping[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Prompt for the API key on initial setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            try:
                title = await self._validate(api_key)
            except AranetAuthError:
                errors["base"] = "invalid_auth"
            except AranetError as err:
                _LOGGER.warning("Aranet validation failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(_account_id(api_key))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=title,
                    data={CONF_API_KEY: api_key},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self,
        entry_data: Mapping[str, Any],
    ) -> ConfigFlowResult:
        """Entry point when HA triggers reauth (e.g. on 401)."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: Mapping[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Prompt for a fresh key during reauth."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            try:
                await self._validate(api_key)
            except AranetAuthError:
                errors["base"] = "invalid_auth"
            except AranetError:
                errors["base"] = "cannot_connect"
            else:
                existing = self._get_reauth_entry()
                return self.async_update_reload_and_abort(
                    existing,
                    data={**existing.data, CONF_API_KEY: api_key},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def _validate(self, api_key: str) -> str:
        """Validate the API key and return a sensible entry title."""
        session = async_get_clientsession(self.hass)
        client = AranetCloudClient(api_key=api_key, session=session)
        sensors = await client.get_sensors()
        bases = await client.get_bases()
        if len(bases) == 1:
            return bases[0].name or DEFAULT_NAME
        return f"{DEFAULT_NAME} ({len(sensors)} sensors)"

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return AranetCloudOptionsFlow(config_entry)


class AranetCloudOptionsFlow(OptionsFlow):
    """Per-entry runtime options — currently just the poll interval."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        # Note: we deliberately do NOT set self.config_entry — HA's
        # OptionsFlow already exposes it as a property since 2024.12.
        self._entry = config_entry

    async def async_step_init(
        self,
        user_input: Mapping[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Show the options form."""
        if user_input is not None:
            return self.async_create_entry(title="", data=dict(user_input))

        current = self._entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SCAN_INTERVAL_SECONDS, max=MAX_SCAN_INTERVAL_SECONDS),
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)


def _account_id(api_key: str) -> str:
    """Stable per-account identifier derived from the key (one-way, salted).

    HA's config-entry unique_id needs *something* per-account to deduplicate
    repeated setups. The API doesn't expose an account ID, and we don't want
    the raw key in HA's storage. SHA-256 with a salt fits the bill.
    """
    return hashlib.sha256(f"aranet_cloud::{api_key}".encode()).hexdigest()[:32]
