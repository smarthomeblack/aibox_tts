"""Config flow for AIBOX TTS."""
from __future__ import annotations

from typing import Any
import logging

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import selector

from .const import (
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_STYLE,
    CONF_VOICE,
    DEFAULT_BASE_URL,
    DEFAULT_STYLE,
    DEFAULT_VOICE,
    DOMAIN,
    TTS_PATH,
    VOICES_PATH,
)

_LOGGER = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate invalid auth."""


async def _async_validate(api_key: str, base_url: str) -> None:
    """Validate API key by calling TTS endpoint with tiny payload."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"text": ".", "voice": "female", "style": "vn_teacher"}
    url = f"{base_url.rstrip('/')}{TTS_PATH}"

    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status in (401, 402):
                    raise InvalidAuth
                if resp.status >= 400:
                    _LOGGER.error("AIBOX validate failed status=%s body=%s", resp.status, await resp.text())
                    raise CannotConnect
                async for _ in resp.content.iter_chunked(128):
                    break
    except aiohttp.ClientError as err:
        _LOGGER.error("AIBOX connection error: %s", err)
        raise CannotConnect from err


async def _async_fetch_voices_catalog(api_key: str, base_url: str) -> dict[str, Any]:
    """Fetch voices catalog from /api/voices."""
    url = f"{base_url.rstrip('/')}{VOICES_PATH}"
    headers = {"Authorization": f"Bearer {api_key}"}

    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status in (401, 402):
                raise InvalidAuth
            if resp.status >= 400:
                raise CannotConnect
            data = await resp.json()
            return data if isinstance(data, dict) else {}


def _build_voice_style_options(catalog: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Build selector options for voices and styles from API response."""
    voices_obj = catalog.get("voices", {}) if isinstance(catalog, dict) else {}

    voice_options: list[dict[str, str]] = []
    style_map: dict[str, str] = {}

    if isinstance(voices_obj, dict):
        for voice_key, voice_info in voices_obj.items():
            if not isinstance(voice_key, str):
                continue

            label = voice_key
            styles_obj: dict[str, Any] = {}
            if isinstance(voice_info, dict):
                label = voice_info.get("label") or voice_key
                styles_obj = voice_info.get("styles", {}) if isinstance(voice_info.get("styles"), dict) else {}

            voice_options.append({"value": voice_key, "label": str(label)})

            for style_key, style_label in styles_obj.items():
                if isinstance(style_key, str):
                    style_map[style_key] = str(style_label) if style_label is not None else style_key

    if not voice_options:
        voice_options = [{"value": DEFAULT_VOICE, "label": DEFAULT_VOICE}]

    style_options = [{"value": k, "label": v} for k, v in sorted(style_map.items(), key=lambda x: x[0])]
    if not style_options:
        style_options = [{"value": DEFAULT_STYLE, "label": DEFAULT_STYLE}]

    return voice_options, style_options


class AiboxTtsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Handle config flow for AIBOX TTS."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return options flow."""
        return AiboxTtsOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle credentials step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            base_url = user_input.get(CONF_BASE_URL, DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL
            try:
                await _async_validate(api_key, base_url)
                await self.async_set_unique_id(f"aibox_tts_{base_url}")
                self._abort_if_unique_id_configured()

                self.context["api_key"] = api_key
                self.context["base_url"] = base_url
                return await self.async_step_profile()
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pragma: no cover
                _LOGGER.exception("Unexpected error in config flow")
                errors["base"] = "unknown"

        schema = vol.Schema(
            {
                vol.Required(CONF_API_KEY): str,
                vol.Optional(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_profile(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle initial voice/style selection."""
        api_key = self.context.get("api_key")
        base_url = self.context.get("base_url", DEFAULT_BASE_URL)
        if not api_key:
            return await self.async_step_user()

        if user_input is not None:
            return self.async_create_entry(
                title="AIBOX TTS",
                data={
                    CONF_API_KEY: api_key,
                    CONF_BASE_URL: base_url,
                },
                options={
                    CONF_VOICE: user_input.get(CONF_VOICE, DEFAULT_VOICE),
                    CONF_STYLE: user_input.get(CONF_STYLE, DEFAULT_STYLE),
                },
            )

        voice_options = [{"value": DEFAULT_VOICE, "label": DEFAULT_VOICE}]
        style_options = [{"value": DEFAULT_STYLE, "label": DEFAULT_STYLE}]
        try:
            catalog = await _async_fetch_voices_catalog(api_key=api_key, base_url=base_url)
            voice_options, style_options = _build_voice_style_options(catalog)
        except Exception as err:
            _LOGGER.warning("Could not auto-load voices/styles in setup flow, fallback to defaults: %s", err)

        schema = vol.Schema(
            {
                vol.Required(CONF_VOICE, default=DEFAULT_VOICE): selector(
                    {
                        "select": {
                            "options": voice_options,
                            "mode": "dropdown",
                            "custom_value": True,
                        }
                    }
                ),
                vol.Required(CONF_STYLE, default=DEFAULT_STYLE): selector(
                    {
                        "select": {
                            "options": style_options,
                            "mode": "dropdown",
                            "custom_value": True,
                        }
                    }
                ),
            }
        )
        return self.async_show_form(step_id="profile", data_schema=schema)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle reconfigure for API key/base URL."""
        errors: dict[str, str] = {}

        entry_id = self.context.get("entry_id")
        if not entry_id:
            return self.async_abort(reason="unknown")

        reconfigure_entry = self.hass.config_entries.async_get_entry(entry_id)
        if reconfigure_entry is None:
            return self.async_abort(reason="unknown")

        if user_input is not None:
            api_key = user_input.get(CONF_API_KEY, "").strip()
            base_url = user_input.get(CONF_BASE_URL, DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL
            try:
                await _async_validate(api_key, base_url)
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={
                        CONF_API_KEY: api_key,
                        CONF_BASE_URL: base_url,
                    },
                    reason="reconfigure_successful",
                )
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error in reconfigure flow")
                errors["base"] = "unknown"

        schema = vol.Schema(
            {
                vol.Required(CONF_API_KEY, default=reconfigure_entry.data.get(CONF_API_KEY, "")): str,
                vol.Optional(
                    CONF_BASE_URL,
                    default=reconfigure_entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL),
                ): str,
            }
        )

        return self.async_show_form(step_id="reconfigure", data_schema=schema, errors=errors)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle reauth flow."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context.get("entry_id"))
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Confirm reauth and update API key."""
        errors: dict[str, str] = {}

        if user_input is not None and self._reauth_entry is not None:
            api_key = user_input.get(CONF_API_KEY, "").strip()
            base_url = self._reauth_entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL)
            try:
                await _async_validate(api_key, base_url)
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data={**self._reauth_entry.data, CONF_API_KEY: api_key},
                )
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error in reauth flow")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )


class AiboxTtsOptionsFlow(OptionsFlow):
    """Handle options flow for AIBOX TTS."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_voice = self._config_entry.options.get(CONF_VOICE, DEFAULT_VOICE)
        current_style = self._config_entry.options.get(CONF_STYLE, DEFAULT_STYLE)

        voice_options = [{"value": DEFAULT_VOICE, "label": DEFAULT_VOICE}]
        style_options = [{"value": DEFAULT_STYLE, "label": DEFAULT_STYLE}]

        try:
            catalog = await _async_fetch_voices_catalog(
                api_key=self._config_entry.data[CONF_API_KEY],
                base_url=self._config_entry.data[CONF_BASE_URL],
            )
            voice_options, style_options = _build_voice_style_options(catalog)
        except Exception as err:
            _LOGGER.warning("Could not auto-load voices/styles from API, fallback to defaults: %s", err)

        schema = vol.Schema(
            {
                vol.Required(CONF_VOICE, default=current_voice): selector(
                    {
                        "select": {
                            "options": voice_options,
                            "mode": "dropdown",
                            "custom_value": True,
                        }
                    }
                ),
                vol.Required(CONF_STYLE, default=current_style): selector(
                    {
                        "select": {
                            "options": style_options,
                            "mode": "dropdown",
                            "custom_value": True,
                        }
                    }
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
