from __future__ import annotations

import asyncio
import secrets
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

import aiohttp

from .auth import AuthenticatedPrincipal
from .config import VoiceSettings
from .errors import UpstreamInvocationError, VoiceHandleError


@dataclass(frozen=True, slots=True)
class VoiceHandle:
    handle: str
    agent_session_id: str
    subject: str
    expires_at_epoch: float
    forward_headers: dict[str, str]
    tone: Literal["professional", "warm", "energetic"]
    user_assertion: str = field(repr=False)


class VoiceHandleStore:
    async def issue(
        self,
        principal: AuthenticatedPrincipal,
        *,
        user_assertion: str,
        forward_headers: dict[str, str],
        tone: Literal["professional", "warm", "energetic"],
    ) -> VoiceHandle: ...

    async def claim(self, handle: str) -> VoiceHandle: ...


class InMemoryVoiceHandleStore(VoiceHandleStore):
    """Short-lived one-replica voice handle store.

    This implementation intentionally keeps state in-memory and is only safe for a
    single application replica.
    """

    def __init__(self, *, ttl_seconds: int, clock: Callable[[], float] = time.time) -> None:
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._lock = asyncio.Lock()
        self._handles: dict[str, VoiceHandle] = {}

    async def issue(
        self,
        principal: AuthenticatedPrincipal,
        *,
        user_assertion: str,
        forward_headers: dict[str, str],
        tone: Literal["professional", "warm", "energetic"],
    ) -> VoiceHandle:
        async with self._lock:
            now = self._clock()
            self._purge_expired(now)
            trusted_headers = dict(forward_headers)
            trusted_headers["x-client-avatar-tone"] = tone
            handle = VoiceHandle(
                handle=secrets.token_urlsafe(32),
                agent_session_id=uuid.uuid4().hex,
                subject=principal.subject,
                expires_at_epoch=now + self._ttl_seconds,
                forward_headers=trusted_headers,
                tone=tone,
                user_assertion=user_assertion,
            )
            self._handles[handle.handle] = handle
            return handle

    async def claim(self, handle: str) -> VoiceHandle:
        async with self._lock:
            now = self._clock()
            self._purge_expired(now)
            claimed = self._handles.pop(handle, None)
            if claimed is None:
                raise VoiceHandleError("The voice handle is invalid or expired")
            return claimed

    def _purge_expired(self, now: float) -> None:
        expired = [key for key, value in self._handles.items() if value.expires_at_epoch <= now]
        for key in expired:
            self._handles.pop(key, None)


@dataclass(slots=True)
class VoiceLiveConnection:
    client: aiohttp.ClientSession
    websocket: aiohttp.ClientWebSocketResponse

    async def close(self) -> None:
        await self.websocket.close()
        await self.client.close()


class VoiceLiveClient:
    def __init__(self, settings: VoiceSettings) -> None:
        self._settings = settings

    async def open(self, ticket: VoiceHandle, *, obo_token: str) -> VoiceLiveConnection:
        client = aiohttp.ClientSession()
        headers = {"Authorization": f"Bearer {obo_token}", **ticket.forward_headers}
        try:
            websocket = await client.ws_connect(
                self._settings.websocket_url,
                headers=headers,
                heartbeat=30,
                max_msg_size=16 * 1024 * 1024,
            )
            await websocket.send_json(self.session_update(ticket))
        except BaseException as exc:
            await client.close()
            raise UpstreamInvocationError("Voice Live connection failed") from exc
        return VoiceLiveConnection(client=client, websocket=websocket)

    def session_update(self, ticket: VoiceHandle) -> dict[str, object]:
        session: dict[str, object] = {
            "modalities": ["text", "audio"],
            "voice": {
                "name": self._settings.voice_name,
                "type": self._settings.voice_type,
            },
            "input_audio_format": "pcm16",
            "input_audio_sampling_rate": 16000,
            "output_audio_format": "pcm16",
            "input_audio_transcription": {
                "model": "azure-speech",
            },
            "turn_detection": {"type": "azure_semantic_vad_multilingual"},
            "input_audio_echo_cancellation": {
                "type": "server_echo_cancellation"
            },
            "input_audio_noise_reduction": {
                "type": "azure_deep_noise_suppression"
            },
        }
        if self._settings.interim_response_enabled:
            session["interim_response"] = {
                "type": "static_interim_response",
                "triggers": ["tool", "latency"],
                "latency_threshold_ms": (
                    self._settings.interim_response_latency_threshold_ms
                ),
                "texts": [
                    "Let me look that up for you.",
                    "I'm checking that now.",
                    "One moment while I pull that together.",
                ],
            }
        if self._settings.avatar_enabled:
            session["avatar"] = {
                "type": "photo-avatar",
                "model": self._settings.avatar_model,
                "character": self._settings.avatar_character,
                "customized": self._settings.avatar_customized,
                "output_protocol": "webrtc",
                "output_audit_audio": False,
                "video": {
                    "codec": "h264",
                    "resolution": {"width": 1920, "height": 1080},
                    "bitrate": 500000,
                },
            }
        return {"type": "session.update", "session": session}
