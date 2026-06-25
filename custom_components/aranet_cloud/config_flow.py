"""Config + reauth flows.

User pastes an API key; we validate it by calling ``get_sensors()`` and
``get_bases()``, then create one entry per account (deduplicated via a
hashed ``unique_id`` so the raw key never lands in HA's registry).

There is no OptionsFlow — HA Core convention says the integration owns its
poll cadence, so :data:`~.const.DEFAULT_SCAN_INTERVAL` is not user-tunable.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from aranet_cloud import AranetAuthError, AranetCloudClient, AranetError

from .const import DEFAULT_NAME, DOMAIN

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

    async def async_step_reconfigure(
        self,
        user_input: Mapping[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Let the user swap in a new API key without removing the entry.

        We can't verify the new key belongs to the *same* account (the
        config-entry ``unique_id`` is a SHA-256 hash of the key itself —
        Aranet exposes no stable account ID), so a rotated key necessarily
        produces a different hash. We validate the key, guard against the
        new hash colliding with a *different* already-configured entry, and
        update the entry in place — same behaviour as the reauth path.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            try:
                await self._validate(api_key)
            except AranetAuthError:
                errors["base"] = "invalid_auth"
            except AranetError as err:
                _LOGGER.warning("Aranet validation failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                # The unique_id is a SHA-256 hash of the key, so a rotated key
                # must re-derive it — otherwise duplicate-account protection
                # tests new setups against the OLD key's hash forever. But if
                # ANOTHER entry already owns the new hash (the same account
                # configured twice, then one rotated onto the other's key),
                # updating would leave two entries with the same unique_id
                # and colliding (DOMAIN, serial) devices — abort instead.
                entry = self._get_reconfigure_entry()
                new_unique_id = _account_id(api_key)
                if self._unique_id_owned_by_other_entry(new_unique_id, entry.entry_id):
                    return self.async_abort(reason="already_configured")
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_API_KEY: api_key},
                    unique_id=new_unique_id,
                )

        return self.async_show_form(
            step_id="reconfigure",
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
            except AranetError as err:
                # Match async_step_user / async_step_reconfigure: log the cause
                # so a reauth that keeps failing to connect leaves a trail.
                _LOGGER.warning("Aranet validation failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                existing = self._get_reauth_entry()
                # Keep the unique_id in step with the rotated key (see the
                # reconfigure step) so adding the same account again still
                # aborts as already_configured — unless a DIFFERENT entry
                # already owns the new key's hash, in which case updating
                # would create a unique_id collision (see reconfigure).
                new_unique_id = _account_id(api_key)
                if self._unique_id_owned_by_other_entry(
                    new_unique_id, existing.entry_id
                ):
                    return self.async_abort(reason="already_configured")
                return self.async_update_reload_and_abort(
                    existing,
                    data={**existing.data, CONF_API_KEY: api_key},
                    unique_id=new_unique_id,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    def _unique_id_owned_by_other_entry(self, unique_id: str, entry_id: str) -> bool:
        """True if a config entry other than ``entry_id`` owns ``unique_id``.

        Guards the reauth/reconfigure unique_id rotation: rotating an entry
        onto a key whose hash is already another entry's unique_id would
        leave two entries with the same unique_id and colliding
        ``(DOMAIN, serial)`` devices.
        """
        return any(
            other.unique_id == unique_id and other.entry_id != entry_id
            for other in self.hass.config_entries.async_entries(DOMAIN)
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


def _account_id(api_key: str) -> str:
    """Stable per-account identifier derived from the key (one-way SHA-256).

    HA's config-entry unique_id needs *something* per-account to deduplicate
    repeated setups. The API doesn't expose an account ID, and we don't want
    the raw key in HA's storage. A SHA-256 digest over a static
    ``aranet_cloud::`` domain-separation prefix plus the key fits the bill: the
    prefix namespaces the digest to this integration — it is not a secret salt
    (it's source-visible), so the key's own entropy is what makes the digest
    infeasible to reverse.
    """
    return hashlib.sha256(f"aranet_cloud::{api_key}".encode()).hexdigest()[:32]
