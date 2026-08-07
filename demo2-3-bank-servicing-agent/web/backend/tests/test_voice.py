from __future__ import annotations

import base64

import pytest

from bank_servicing_backend.app import _browser_voice_frame, _voice_live_audio_event
from bank_servicing_backend.auth import AuthenticatedPrincipal
from bank_servicing_backend.config import VoiceSettings
from bank_servicing_backend.voice import InMemoryVoiceHandleStore


@pytest.mark.asyncio
async def test_voice_handle_is_single_use() -> None:
    store = InMemoryVoiceHandleStore(ttl_seconds=120)
    principal = AuthenticatedPrincipal(
        subject="subject-1",
        object_id="object-1",
        tenant_id="tenant-id",
        username="person@example.com",
        roles=frozenset(),
        scopes=frozenset(),
        token="user-token",
    )

    handle = await store.issue(principal, user_assertion="user-token", forward_headers={})
    claimed = await store.claim(handle.handle)

    assert claimed.handle == handle.handle
    with pytest.raises(Exception):
        await store.claim(handle.handle)


@pytest.mark.asyncio
async def test_voice_handle_expires() -> None:
    current = 1000.0

    def clock() -> float:
        return current

    store = InMemoryVoiceHandleStore(ttl_seconds=10, clock=clock)
    principal = AuthenticatedPrincipal(
        subject="subject-1",
        object_id="object-1",
        tenant_id="tenant-id",
        username="person@example.com",
        roles=frozenset(),
        scopes=frozenset(),
        token="user-token",
    )

    handle = await store.issue(principal, user_assertion="user-token", forward_headers={})
    current = 1011.0

    with pytest.raises(Exception):
        await store.claim(handle.handle)


def test_voice_live_url_targets_new_hosted_agent_contract() -> None:
    settings = VoiceSettings(
        endpoint="https://example.services.ai.azure.com",
        api_version="2026-04-10",
        project_name="4iq-foundry-project",
        agent_name="bank-servicing-agent",
        voice_name="en-US-Davis:DragonHDLatestNeural",
        handle_ttl_seconds=120,
    )

    assert settings.websocket_url == (
        "https://example.services.ai.azure.com/voice-live/realtime"
        "?api-version=2026-04-10"
        "&agent-name=bank-servicing-agent"
        "&agent-project-name=4iq-foundry-project"
    )


def test_browser_audio_is_wrapped_for_voice_live() -> None:
    audio = b"\x01\x02\x03\x04"

    assert _voice_live_audio_event(audio) == {
        "type": "input_audio_buffer.append",
        "audio": base64.b64encode(audio).decode("ascii"),
    }


def test_voice_live_events_are_translated_for_browser() -> None:
    audio = b"\x01\x02"

    assert _browser_voice_frame(
        {"type": "response.audio.delta", "delta": base64.b64encode(audio).decode("ascii")}
    ) == ("bytes", audio)
    assert _browser_voice_frame(
        {
            "type": "conversation.item.input_audio_transcription.completed",
            "transcript": "Compare checking and savings.",
        }
    ) == (
        "json",
        {
            "type": "transcript",
            "role": "user",
            "text": "Compare checking and savings.",
        },
    )
    assert _browser_voice_frame(
        {
            "type": "response.audio_transcript.done",
            "transcript": "Checking is designed for everyday spending.",
        }
    ) == (
        "json",
        {
            "type": "transcript",
            "role": "assistant",
            "text": "Checking is designed for everyday spending.",
        },
    )
    assert _browser_voice_frame(
        {
            "type": "error",
            "error": {"message": "The voice configuration is invalid."},
        }
    ) == (
        "json",
        {
            "type": "error",
            "message": "The voice configuration is invalid.",
        },
    )
