"""AIBOX TTS engine client."""
from __future__ import annotations

import asyncio
import io
import logging
import struct
import time
import wave
from typing import Any, AsyncGenerator

import aiohttp
from homeassistant.exceptions import HomeAssistantError

from .const import DEFAULT_STYLE, DEFAULT_VOICE, TTS_PATH, VOICES_PATH

_LOGGER = logging.getLogger(__name__)


class AiboxTTSEngine:
    """Client wrapper for AIBOX TTS HTTP APIs."""

    def __init__(self, api_key: str, base_url: str) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    @property
    def headers(self) -> dict[str, str]:
        """Return auth headers."""
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def async_get_voices(self) -> dict[str, Any]:
        """Fetch voice/style catalog from AIBOX."""
        url = f"{self._base_url}{VOICES_PATH}"
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers={"Authorization": f"Bearer {self._api_key}"}) as resp:
                if resp.status >= 400:
                    raise HomeAssistantError(f"Failed to fetch voices: {resp.status}")
                return await resp.json()

    async def async_tts_pcm(self, text: str, voice: str | None = None, style: str | None = None) -> bytes:
        """Generate TTS and return raw PCM bytes."""
        chunks = bytearray()
        async for chunk in self.async_tts_pcm_stream(text=text, voice=voice, style=style):
            chunks.extend(chunk)
        return bytes(chunks)

    async def async_tts_pcm_stream(
        self,
        text: str,
        voice: str | None = None,
        style: str | None = None,
    ) -> AsyncGenerator[bytes, None]:
        """Generate TTS and yield PCM chunks as they arrive from API."""
        payload = {
            "text": text,
            "voice": voice or DEFAULT_VOICE,
            "style": style or DEFAULT_STYLE,
        }
        url = f"{self._base_url}{TTS_PATH}"

        timeout = aiohttp.ClientTimeout(total=120)
        retries = 2
        last_error: Exception | None = None

        req_started = time.monotonic()
        _LOGGER.info(
            "[AIBOX][stream] request_start voice=%s style=%s text_len=%d",
            payload["voice"],
            payload["style"],
            len(text),
        )

        for attempt in range(retries + 1):
            try:
                _LOGGER.debug("[AIBOX][stream] attempt=%d", attempt + 1)

                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url, headers=self.headers, json=payload) as resp:
                        ttfb_ms = (time.monotonic() - req_started) * 1000
                        _LOGGER.info(
                            "[AIBOX][stream] response status=%s ttfb=%.0fms",
                            resp.status,
                            ttfb_ms,
                        )

                        if resp.status in (401, 402):
                            raise HomeAssistantError("AIBOX auth/balance error")
                        if resp.status >= 400:
                            body = await resp.text()
                            raise HomeAssistantError(f"AIBOX TTS error {resp.status}: {body}")

                        first_chunk_time: float | None = None
                        chunk_count = 0
                        byte_count = 0

                        async for chunk in resp.content.iter_any():
                            if not chunk:
                                continue

                            now = time.monotonic()
                            chunk_count += 1
                            byte_count += len(chunk)

                            if first_chunk_time is None:
                                first_chunk_time = now
                                first_chunk_ms = (first_chunk_time - req_started) * 1000
                                _LOGGER.info(
                                    "[AIBOX][stream] first_chunk after=%.0fms size=%d",
                                    first_chunk_ms,
                                    len(chunk),
                                )

                            if chunk_count % 50 == 0:
                                elapsed_ms = (now - req_started) * 1000
                                _LOGGER.debug(
                                    "[AIBOX][stream] progress chunks=%d bytes=%d elapsed=%.0fms",
                                    chunk_count,
                                    byte_count,
                                    elapsed_ms,
                                )

                            yield chunk

                        total_ms = (time.monotonic() - req_started) * 1000
                        _LOGGER.info(
                            "[AIBOX][stream] completed chunks=%d bytes=%d total=%.0fms",
                            chunk_count,
                            byte_count,
                            total_ms,
                        )
                        return

            except Exception as err:
                last_error = err
                _LOGGER.warning("[AIBOX][stream] attempt=%d failed: %s", attempt + 1, err)
                if attempt < retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
                else:
                    break

        raise HomeAssistantError(f"AIBOX TTS request failed: {last_error}")

    async def async_tts_wav_stream(
        self,
        text: str,
        voice: str | None = None,
        style: str | None = None,
        sample_rate: int = 24000,
        channels: int = 1,
        sample_width: int = 2,
    ) -> AsyncGenerator[bytes, None]:
        """Yield WAV stream (header first, then PCM chunks)."""
        yield self.wav_stream_header(sample_rate, channels, sample_width)
        async for pcm_chunk in self.async_tts_pcm_stream(text=text, voice=voice, style=style):
            yield pcm_chunk

    @staticmethod
    def wav_stream_header(sample_rate: int, channels: int, sample_width: int) -> bytes:
        """Create WAV header for streaming with unknown total length."""
        byte_rate = sample_rate * channels * sample_width
        block_align = channels * sample_width
        bits_per_sample = sample_width * 8

        data_size = 0xFFFFFFFF
        riff_size = 36 + data_size

        return b"".join(
            [
                b"RIFF",
                struct.pack("<I", riff_size & 0xFFFFFFFF),
                b"WAVE",
                b"fmt ",
                struct.pack("<I", 16),
                struct.pack("<H", 1),
                struct.pack("<H", channels),
                struct.pack("<I", sample_rate),
                struct.pack("<I", byte_rate),
                struct.pack("<H", block_align),
                struct.pack("<H", bits_per_sample),
                b"data",
                struct.pack("<I", data_size),
            ]
        )

    @staticmethod
    def pcm_to_wav(
        pcm_data: bytes,
        sample_rate: int = 24000,
        channels: int = 1,
        sample_width: int = 2,
    ) -> bytes:
        """Wrap raw PCM bytes to WAV bytes for Home Assistant playback."""
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_data)
        return buffer.getvalue()
