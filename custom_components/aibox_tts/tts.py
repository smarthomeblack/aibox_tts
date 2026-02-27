"""TTS platform for AIBOX TTS."""
from __future__ import annotations

from typing import Any, AsyncGenerator
import logging
import time

from homeassistant.components.tts import (
    ATTR_LANGUAGE,
    TextToSpeechEntity,
    TTSAudioRequest,
    TTSAudioResponse,
    Voice,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .aibox_engine import AiboxTTSEngine
from .const import (
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_STYLE,
    CONF_VOICE,
    DEFAULT_STYLE,
    DEFAULT_VOICE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AIBOX TTS entity from config entry."""
    engine = AiboxTTSEngine(
        api_key=entry.data[CONF_API_KEY],
        base_url=entry.data[CONF_BASE_URL],
    )
    async_add_entities([AiboxTTSEntity(entry, engine)])


class AiboxTTSEntity(TextToSpeechEntity):
    """AIBOX TTS entity."""

    _attr_name = "AIBOX TTS"
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, engine: AiboxTTSEngine) -> None:
        """Init entity."""
        self._entry = entry
        self._engine = engine
        self._attr_unique_id = f"aibox_tts_{entry.entry_id}"

        self._voice_catalog: dict[str, Any] = {}
        self._voice_values: list[str] = [DEFAULT_VOICE]
        self._style_values: list[str] = [DEFAULT_STYLE]
        self._supported_voices: list[Voice] = [Voice(DEFAULT_VOICE, DEFAULT_VOICE)]

    async def async_added_to_hass(self) -> None:
        """Fetch dynamic voices/styles once entity is added."""
        await super().async_added_to_hass()
        await self._async_refresh_voice_catalog()

    async def _async_refresh_voice_catalog(self) -> None:
        """Load voice catalog from API for UI hints and runtime options."""
        try:
            data = await self._engine.async_get_voices()
            voices = data.get("voices", {}) if isinstance(data, dict) else {}

            voice_values: list[str] = []
            style_values: list[str] = []
            supported_voices: list[Voice] = []

            if isinstance(voices, dict):
                for voice_key, voice_info in voices.items():
                    if not isinstance(voice_key, str):
                        continue

                    voice_values.append(voice_key)
                    voice_label = voice_key
                    styles: dict[str, Any] = {}

                    if isinstance(voice_info, dict):
                        voice_label = str(voice_info.get("label") or voice_key)
                        raw_styles = voice_info.get("styles", {})
                        if isinstance(raw_styles, dict):
                            styles = raw_styles

                    # Build one combined voice list for HA UI: "voice|style"
                    if styles:
                        for style_key, style_label in styles.items():
                            if not isinstance(style_key, str):
                                continue
                            style_values.append(style_key)
                            label = f"{voice_label} - {style_label}"
                            value = f"{voice_key}|{style_key}"
                            supported_voices.append(Voice(value, label))
                    else:
                        supported_voices.append(Voice(voice_key, voice_label))

            self._voice_catalog = voices if isinstance(voices, dict) else {}
            self._voice_values = sorted(set(voice_values)) or [DEFAULT_VOICE]
            self._style_values = sorted(set(style_values)) or [DEFAULT_STYLE]
            self._supported_voices = supported_voices or [Voice(DEFAULT_VOICE, DEFAULT_VOICE)]
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.warning("Could not load AIBOX voice catalog: %s", err)

    @staticmethod
    def _resolve_voice_style(
        voice_option: str | None,
        style_option: str | None,
    ) -> tuple[str, str]:
        """Resolve voice/style from options.

        Supports combined voice value `voice|style` for HA voice selector.
        """
        voice = voice_option or DEFAULT_VOICE
        style = style_option or DEFAULT_STYLE

        if isinstance(voice, str) and "|" in voice:
            base_voice, base_style = voice.split("|", 1)
            if base_voice:
                voice = base_voice
            if base_style:
                style = base_style

        return voice, style

    @property
    def default_language(self) -> str:
        """Return default language."""
        return "vi"

    @property
    def supported_languages(self) -> list[str]:
        """Return supported languages."""
        return ["vi"]

    @property
    def supported_options(self) -> list[str]:
        """Return supported options for service/pipeline UI."""
        return [ATTR_LANGUAGE, CONF_VOICE, CONF_STYLE]

    @property
    def default_options(self) -> dict[str, Any]:
        """Return default options."""
        return {
            ATTR_LANGUAGE: "vi",
            CONF_VOICE: self._entry.options.get(CONF_VOICE, DEFAULT_VOICE),
            CONF_STYLE: self._entry.options.get(CONF_STYLE, DEFAULT_STYLE),
        }

    @callback
    def async_get_supported_voices(self, language: str) -> list[Voice] | None:
        """Return supported voices for the given language.

        This is what HA UI uses to build the voice dropdown in media/assistant flows.
        """
        if language != "vi":
            return None
        return self._supported_voices

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose voices/styles so HA UI and users can inspect available options."""
        return {
            "available_voices": self._voice_values,
            "available_styles": self._style_values,
            "voice_catalog": self._voice_catalog,
            "supported_voices_dropdown": [
                {"voice": v.voice_id, "name": v.name} for v in self._supported_voices
            ],
        }

    @property
    def device_info(self) -> dict[str, Any]:
        """Attach TTS entity to integration device."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "AIBOX TTS",
            "manufacturer": "smarthomeblack",
            "model": "AIBOX TTS",
            "configuration_url": self._entry.data.get(CONF_BASE_URL),
        }

    async def async_stream_tts_audio(self, request: TTSAudioRequest) -> TTSAudioResponse:
        """Stream WAV chunks to Home Assistant as data arrives from AIBOX."""
        stream_started = time.monotonic()

        options = request.options or {}
        raw_voice = options.get(CONF_VOICE, self._entry.options.get(CONF_VOICE, DEFAULT_VOICE))
        raw_style = options.get(CONF_STYLE, self._entry.options.get(CONF_STYLE, DEFAULT_STYLE))
        voice, style = self._resolve_voice_style(raw_voice, raw_style)

        parts: list[str] = []
        async for part in request.message_gen:
            if part:
                parts.append(part)
        text = "".join(parts).strip()

        text_ready_ms = (time.monotonic() - stream_started) * 1000
        _LOGGER.info(
            "[AIBOX][ha] stream_start text_ready=%.0fms text_len=%d voice=%s style=%s",
            text_ready_ms,
            len(text),
            voice,
            style,
        )

        async def wav_generator() -> AsyncGenerator[bytes, None]:
            first_yield_time: float | None = None
            chunk_count = 0
            total_bytes = 0

            async for chunk in self._engine.async_tts_wav_stream(text=text, voice=voice, style=style):
                now = time.monotonic()
                chunk_count += 1
                total_bytes += len(chunk)

                if first_yield_time is None:
                    first_yield_time = now
                    first_yield_ms = (first_yield_time - stream_started) * 1000
                    _LOGGER.info(
                        "[AIBOX][ha] first_yield after=%.0fms size=%d",
                        first_yield_ms,
                        len(chunk),
                    )

                if chunk_count % 50 == 0:
                    elapsed_ms = (now - stream_started) * 1000
                    _LOGGER.debug(
                        "[AIBOX][ha] yield_progress chunks=%d bytes=%d elapsed=%.0fms",
                        chunk_count,
                        total_bytes,
                        elapsed_ms,
                    )

                yield chunk

            total_ms = (time.monotonic() - stream_started) * 1000
            _LOGGER.info(
                "[AIBOX][ha] stream_done chunks=%d bytes=%d total=%.0fms",
                chunk_count,
                total_bytes,
                total_ms,
            )

        return TTSAudioResponse(extension="wav", data_gen=wav_generator())

    async def async_get_tts_audio(
        self,
        message: str,
        language: str,
        options: dict[str, Any] | None = None,
    ) -> tuple[str | None, bytes | None]:
        """Generate WAV audio from AIBOX PCM stream."""
        try:
            options = options or {}
            raw_voice = options.get(CONF_VOICE, self._entry.options.get(CONF_VOICE, DEFAULT_VOICE))
            raw_style = options.get(CONF_STYLE, self._entry.options.get(CONF_STYLE, DEFAULT_STYLE))
            voice, style = self._resolve_voice_style(raw_voice, raw_style)

            pcm = await self._engine.async_tts_pcm(
                text=message,
                voice=voice,
                style=style,
            )
            wav = self._engine.pcm_to_wav(pcm)
            return "wav", wav
        except Exception as err:
            _LOGGER.error("AIBOX TTS generation failed: %s", err)
            return None, None
