"""Config flow for Aranet Cloud — API key entry + validation.

Single-step flow:

1. User enters their API key.
2. We call ``get_sensors()`` to verify the key works.
3. On success: create a config entry, named after the discovered base
   station (or a default if zero bases).

A re-auth flow is triggered when the coordinator surfaces
:class:`ConfigEntryAuthFailed` — the user is shown the same form again.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from aranet_cloud import AranetAuthError, AranetCloudClient, AranetError
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})


class AranetCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the UI configuration flow."""

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
                # One entry per API key — repeat sets are de-duped.
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
        """Entry point when HA triggers reauth (e.g. on 401 from API)."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: Mapping[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Prompt for a fresh API key during reauth."""
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
        """Hit the API to verify the key. Returns the entry title to use."""
        session = async_get_clientsession(self.hass)
        client = AranetCloudClient(api_key=api_key, session=session)
        sensors = await client.get_sensors()
        bases = await client.get_bases()
        # Title: base-station name if exactly one, else a generic label that
        # includes the sensor count. Account-scoped, not key-scoped — keeps
        # the UI readable when the user rotates their key.
        if len(bases) == 1:
            return bases[0].name or DEFAULT_NAME
        return f"{DEFAULT_NAME} ({len(sensors)} sensors)"


def _account_id(api_key: str) -> str:
    """A stable, non-reversible identifier for an account, derived from the key.

    HA's config-entry unique_id needs *something* per-account to deduplicate
    repeated setups. The API itself doesn't expose an account ID — and we
    don't want to store the raw key in the entry's unique_id. A salted
    SHA-256 hash gives us stable per-account identity without leaking the
    key into HA's storage.
    """
    import hashlib

    return hashlib.sha256(f"aranet_cloud::{api_key}".encode()).hexdigest()[:32]
