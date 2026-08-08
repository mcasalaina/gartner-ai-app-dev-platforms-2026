from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from aiohttp import WSMsgType
from fastapi import Depends, FastAPI, Header, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .auth import AuthenticatedPrincipal, EntraJwtValidator, require_any_role
from .config import AppSettings
from .errors import AuthenticationError, BackendError, ModeValidationError, VoiceHandleError
from .foundry import ChatMessage, Citation, FoundryResponsesClient
from .headers import extract_forward_headers
from .obo import OboTokenProvider
from .stores import (
    InMemoryConversationStore,
    InMemoryReviewStore,
    QualityMetricsSnapshot,
)
from .telemetry import configure_telemetry
from .voice import InMemoryVoiceHandleStore, VoiceHandleStore, VoiceLiveClient

logger = logging.getLogger(__name__)
_ALLOWED_COMPARE_MODELS = ("gpt-5.4-mini", "gpt-5-mini", "gpt-4.1-mini")


class RequestMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant", "system", "developer"]
    content: str = Field(min_length=1)


class HistoryChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    messages: list[RequestMessage] = Field(min_length=1)


class CompatibilityChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["service_discovery", "customer_servicing"]
    content: str = Field(min_length=1)
    conversation_id: str | None = Field(default=None, alias="conversationId")


class VoiceHandleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_context: str = Field(alias="clientContext")
    tone: Literal["professional", "warm", "energetic"] = "professional"


class LegacyFeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    call_id: str = Field(alias="callId", min_length=1)
    rating: int = Field(ge=1, le=5)
    comment: str | None = None


class CompatibilityFeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: str = Field(alias="messageId", min_length=1)
    sentiment: Literal["positive", "negative"]


class EvaluateCompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(min_length=1)


class ContentReviewResponse(BaseModel):
    id: str
    title: str
    status: Literal["pending_review", "approved", "rejected", "published"]
    version: int
    summary: str


class MetricsResponse(BaseModel):
    comprehensiveness: float | None
    accuracy: float | None
    latencyP50Ms: float | None
    estimatedCostUsd: float | None


class MessageCitationResponse(BaseModel):
    id: str
    title: str
    url: str | None = None


class ChatMessageResponse(BaseModel):
    id: str
    role: Literal["assistant"]
    content: str
    createdAt: str
    citations: list[MessageCitationResponse]
    queriedSources: list[Literal["Fabric IQ", "Foundry IQ", "Work IQ"]]
    groundingSources: list[Literal["Fabric IQ", "Foundry IQ", "Work IQ"]]
    traceId: str


class ChatQualityResponse(BaseModel):
    passed: bool
    repaired: bool
    citationCount: int


class CompatibilityChatResponse(BaseModel):
    message: ChatMessageResponse
    quality: ChatQualityResponse
    conversationId: str


class HistoryChatResponse(BaseModel):
    text: str
    responseId: str


class FeedbackResponse(BaseModel):
    status: Literal["accepted"]
    messageId: str
    sentiment: Literal["positive", "negative"]
    rating: int


class CompareModelResponse(BaseModel):
    model: Literal["gpt-5.4-mini", "gpt-5-mini", "gpt-4.1-mini"]
    output: str
    rubricScore: float | None
    assertScore: float | None
    latencyMs: float
    estimatedCostUsd: float | None


@dataclass(slots=True)
class RequestMetrics:
    feedback_count: int = 0
    review_count: int = 0
    chat_count: int = 0
    voice_handle_count: int = 0


@dataclass(slots=True)
class AppServices:
    settings: AppSettings
    validator: EntraJwtValidator
    obo_provider: OboTokenProvider
    foundry_client: FoundryResponsesClient
    voice_handles: VoiceHandleStore
    voice_client: VoiceLiveClient
    request_metrics: RequestMetrics
    conversations: InMemoryConversationStore
    review_store: InMemoryReviewStore
    quality_metrics: QualityMetricsSnapshot


def create_app(
    settings: AppSettings,
    *,
    validator: EntraJwtValidator | None = None,
    obo_provider: OboTokenProvider | None = None,
    foundry_client: FoundryResponsesClient | None = None,
    voice_handles: VoiceHandleStore | None = None,
    voice_client: VoiceLiveClient | None = None,
    request_metrics: RequestMetrics | None = None,
    conversations: InMemoryConversationStore | None = None,
    review_store: InMemoryReviewStore | None = None,
    quality_metrics: QualityMetricsSnapshot | None = None,
) -> FastAPI:
    app = FastAPI(title="Bank Servicing Backend", version="0.2.0")
    app.state.services = AppServices(
        settings=settings,
        validator=validator or EntraJwtValidator(settings.entra),
        obo_provider=obo_provider or OboTokenProvider(settings.entra),
        foundry_client=foundry_client or FoundryResponsesClient(settings.foundry),
        voice_handles=voice_handles or InMemoryVoiceHandleStore(ttl_seconds=settings.voice.handle_ttl_seconds),
        voice_client=voice_client or VoiceLiveClient(settings.voice),
        request_metrics=request_metrics or RequestMetrics(),
        conversations=conversations or InMemoryConversationStore(),
        review_store=review_store or InMemoryReviewStore(),
        quality_metrics=quality_metrics or QualityMetricsSnapshot(),
    )

    @app.exception_handler(BackendError)
    async def handle_backend_error(_request: Request, exc: BackendError) -> JSONResponse:
        return JSONResponse(
            {
                "detail": exc.message,
                "error": {"code": exc.error_code, "message": exc.message},
            },
            status_code=exc.status_code,
            headers={"Cache-Control": "no-store"},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled backend error", exc_info=exc)
        return JSONResponse(
            {
                "detail": "An unexpected error occurred.",
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred.",
                },
            },
            status_code=500,
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/app-config")
    async def app_config() -> dict[str, Any]:
        current = app.state.services.settings
        return {
            "environment": current.environment,
            "allowedDemoModes": list(current.demo_modes),
            "voice": {
                "enabled": True,
                "avatar": {
                    "enabled": current.voice.avatar_enabled,
                    "character": current.voice.avatar_character,
                    "model": current.voice.avatar_model,
                },
                "handlePath": "/api/voice/handles",
                "websocketPath": "/api/voice/live",
                "authMessage": {"type": "auth", "sessionHandle": "<handle>"},
            },
        }

    @app.post("/api/chat", response_model=CompatibilityChatResponse)
    async def chat(
        body: CompatibilityChatRequest,
        request: Request,
        principal: Annotated[AuthenticatedPrincipal, Depends(_require_user)],
    ) -> CompatibilityChatResponse:
        services = request.app.state.services
        started = time.perf_counter()
        forward_headers = extract_forward_headers(
            request.headers,
            allowed_demo_modes=services.settings.demo_modes,
            demo_mode=body.mode,
        )
        conversation_id, history = services.conversations.build_request(body.conversation_id, body.content)
        obo_token = await services.obo_provider.acquire(principal.token)
        reply = await services.foundry_client.create_response(
            bearer_token=obo_token,
            history=history,
            forward_headers=forward_headers,
        )
        services.conversations.record_response(conversation_id, body.content, reply)
        services.request_metrics.chat_count += 1
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        services.quality_metrics.record_latency(latency_ms)
        created_at = datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
        citations = [_citation_response(item) for item in reply.citations]
        logger.info(
            "bank_chat mode=%s model=%s citations=%d latency_ms=%.2f response_id=%s",
            body.mode,
            services.settings.foundry.model_name,
            len(citations),
            latency_ms,
            reply.response_id,
        )
        return CompatibilityChatResponse(
            message=ChatMessageResponse(
                id=reply.response_id,
                role="assistant",
                content=reply.text,
                createdAt=created_at,
                citations=citations,
                queriedSources=list(reply.queried_sources),
                groundingSources=list(reply.grounding_sources),
                traceId=reply.response_id,
            ),
            quality=ChatQualityResponse(
                passed=bool(reply.text.strip()),
                repaired=False,
                citationCount=len(citations),
            ),
            conversationId=conversation_id,
        )

    @app.post("/api/chat/history", response_model=HistoryChatResponse)
    async def chat_history(
        body: HistoryChatRequest,
        request: Request,
        principal: Annotated[AuthenticatedPrincipal, Depends(_require_user)],
    ) -> HistoryChatResponse:
        services = request.app.state.services
        forward_headers = extract_forward_headers(
            request.headers,
            allowed_demo_modes=services.settings.demo_modes,
        )
        obo_token = await services.obo_provider.acquire(principal.token)
        reply = await services.foundry_client.create_response(
            bearer_token=obo_token,
            history=[ChatMessage(role=item.role, content=item.content) for item in body.messages],
            forward_headers=forward_headers,
        )
        services.request_metrics.chat_count += 1
        return HistoryChatResponse(text=reply.text, responseId=reply.response_id)

    @app.post("/api/voice/handles", status_code=201)
    async def create_voice_handle(
        body: VoiceHandleRequest,
        request: Request,
        principal: Annotated[AuthenticatedPrincipal, Depends(_require_user)],
    ) -> JSONResponse:
        if body.client_context != "web":
            raise VoiceHandleError("The voice session request has an invalid client context")
        services = request.app.state.services
        forward_headers = extract_forward_headers(
            request.headers,
            allowed_demo_modes=services.settings.demo_modes,
        )
        ticket = await services.voice_handles.issue(
            principal,
            user_assertion=principal.token,
            forward_headers=forward_headers,
            tone=body.tone,
        )
        services.request_metrics.voice_handle_count += 1
        return JSONResponse(
            {
                "sessionHandle": ticket.handle,
                "agentSessionId": ticket.agent_session_id,
                "expiresAt": datetime.fromtimestamp(ticket.expires_at_epoch, tz=UTC)
                .isoformat()
                .replace("+00:00", "Z"),
            },
            status_code=201,
            headers={"Cache-Control": "no-store"},
        )

    @app.websocket("/api/voice/live")
    async def voice_live(websocket: WebSocket) -> None:
        await websocket.accept()
        services = websocket.app.state.services
        try:
            first_frame = await asyncio.wait_for(websocket.receive_text(), timeout=5)
            payload = json.loads(first_frame)
            handle = _parse_voice_auth_frame(payload)
            ticket = await services.voice_handles.claim(handle)
            obo_token = await services.obo_provider.acquire(ticket.user_assertion)
            upstream = await services.voice_client.open(ticket, obo_token=obo_token)
        except (TimeoutError, ValueError, VoiceHandleError, AuthenticationError) as exc:
            await websocket.send_json({"type": "error", "message": str(exc)})
            await websocket.close(code=1008)
            return
        except BackendError as exc:
            await websocket.send_json({"type": "error", "message": exc.message})
            await websocket.close(code=1011)
            return

        try:
            await _relay_voice(websocket, upstream.websocket)
        finally:
            await upstream.close()

    @app.post("/api/feedback", response_model=FeedbackResponse)
    async def feedback(
        request: Request,
        principal: Annotated[AuthenticatedPrincipal, Depends(_require_user)],
    ) -> FeedbackResponse:
        payload = await request.json()
        parsed = _parse_feedback(payload)
        request.app.state.services.request_metrics.feedback_count += 1
        sentiment = parsed["sentiment"]
        message_id = parsed["message_id"]
        rating = parsed["rating"]
        logger.info(
            "bank_feedback message_id=%s sentiment=%s rating=%d",
            message_id,
            sentiment,
            rating,
        )
        return FeedbackResponse(
            status="accepted",
            messageId=message_id,
            sentiment=sentiment,
            rating=rating,
        )

    @app.get("/api/admin/metrics", response_model=MetricsResponse)
    async def admin_metrics(
        request: Request,
        _principal: Annotated[AuthenticatedPrincipal, Depends(_require_reviewer_or_admin)],
    ) -> MetricsResponse:
        snapshot = request.app.state.services.quality_metrics
        return MetricsResponse(
            comprehensiveness=snapshot.comprehensiveness,
            accuracy=snapshot.accuracy,
            latencyP50Ms=snapshot.latency_p50_ms,
            estimatedCostUsd=snapshot.estimated_cost_usd,
        )

    @app.get("/api/admin/content/reviews", response_model=list[ContentReviewResponse])
    async def admin_content_reviews(
        request: Request,
        _principal: Annotated[AuthenticatedPrincipal, Depends(_require_reviewer_or_admin)],
    ) -> list[ContentReviewResponse]:
        drafts = request.app.state.services.review_store.list()
        return [
            ContentReviewResponse(
                id=draft.id,
                title=draft.title,
                status=draft.status,
                version=draft.version,
                summary=draft.summary,
            )
            for draft in drafts
        ]

    @app.post(
        "/api/admin/content/reviews/{draft_id}/{decision}",
        response_model=ContentReviewResponse,
    )
    async def admin_decide_review(
        draft_id: str,
        decision: Literal["approve", "reject"],
        request: Request,
        _principal: Annotated[AuthenticatedPrincipal, Depends(_require_reviewer_or_admin)],
    ) -> ContentReviewResponse:
        draft = request.app.state.services.review_store.decide(draft_id, decision)
        request.app.state.services.request_metrics.review_count += 1
        logger.info(
            "bank_content_review draft_id=%s decision=%s version=%d",
            draft_id,
            decision,
            draft.version,
        )
        return ContentReviewResponse(
            id=draft.id,
            title=draft.title,
            status=draft.status,
            version=draft.version,
            summary=draft.summary,
        )

    @app.post("/api/admin/evaluations/compare", response_model=list[CompareModelResponse])
    async def admin_compare(
        body: EvaluateCompareRequest,
        request: Request,
        principal: Annotated[AuthenticatedPrincipal, Depends(_require_admin)],
    ) -> list[CompareModelResponse]:
        services = request.app.state.services
        forward_headers = extract_forward_headers(
            request.headers,
            allowed_demo_modes=services.settings.demo_modes,
        )
        obo_token = await services.obo_provider.acquire(principal.token)
        results: list[CompareModelResponse] = []
        for model_name in _ALLOWED_COMPARE_MODELS:
            started = time.perf_counter()
            reply = await services.foundry_client.create_response(
                bearer_token=obo_token,
                history=[ChatMessage(role="user", content=body.prompt)],
                forward_headers=forward_headers,
                model_override=model_name,
            )
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            results.append(
                CompareModelResponse(
                    model=model_name,
                    output=reply.text,
                    rubricScore=None,
                    assertScore=None,
                    latencyMs=latency_ms,
                    estimatedCostUsd=None,
                )
            )
        return results

    @app.get("/api/admin/overview")
    async def admin_overview(
        request: Request,
        _principal: Annotated[AuthenticatedPrincipal, Depends(_require_admin)],
    ) -> dict[str, Any]:
        current = request.app.state.services.settings
        metrics = request.app.state.services.request_metrics
        return {
            "environment": current.environment,
            "reviewerRoleCount": len(current.roles.reviewer_roles),
            "adminRoleCount": len(current.roles.admin_roles),
            "voiceHandleTtlSeconds": current.voice.handle_ttl_seconds,
            "allowedDemoModes": list(current.demo_modes),
            "chatCount": metrics.chat_count,
            "feedbackCount": metrics.feedback_count,
            "reviewCount": metrics.review_count,
        }

    return app


def create_default_app() -> FastAPI:
    configure_telemetry()
    logging.basicConfig(level=logging.INFO)
    return create_app(AppSettings.from_environment())


async def _require_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> AuthenticatedPrincipal:
    if not authorization:
        raise AuthenticationError("A bearer access token is required")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AuthenticationError("A bearer access token is required")
    return await request.app.state.services.validator.validate(token)


async def _require_reviewer_or_admin(
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(_require_user)],
) -> AuthenticatedPrincipal:
    require_any_role(principal, frozenset(request.app.state.services.settings.roles.reviewer_or_admin))
    return principal


async def _require_admin(
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(_require_user)],
) -> AuthenticatedPrincipal:
    require_any_role(principal, frozenset(request.app.state.services.settings.roles.admin_roles))
    return principal


async def _relay_voice(browser: WebSocket, upstream: Any) -> None:
    async def browser_to_upstream() -> None:
        try:
            while True:
                message = await browser.receive()
                message_type = message["type"]
                if message_type == "websocket.receive":
                    if message.get("bytes") is not None:
                        await upstream.send_json(_voice_live_audio_event(message["bytes"]))
                    elif message.get("text") is not None:
                        await upstream.send_json(
                            _voice_live_control_event(json.loads(message["text"]))
                        )
                elif message_type == "websocket.disconnect":
                    return
        except WebSocketDisconnect:
            return

    async def upstream_to_browser() -> None:
        async for message in upstream:
            if message.type == WSMsgType.TEXT:
                try:
                    payload = json.loads(message.data)
                except ValueError as exc:
                    raise BackendError("Voice Live returned invalid JSON") from exc
                frame = _browser_voice_frame(payload)
                if frame is None:
                    continue
                frame_type, frame_payload = frame
                if frame_type == "bytes":
                    await browser.send_bytes(frame_payload)
                else:
                    await browser.send_json(frame_payload)
            elif message.type == WSMsgType.BINARY:
                await browser.send_bytes(message.data)
            elif message.type in {WSMsgType.CLOSE, WSMsgType.CLOSED}:
                return
            elif message.type == WSMsgType.ERROR:
                raise BackendError("Voice Live closed with an error")

    tasks = {
        asyncio.create_task(browser_to_upstream()),
        asyncio.create_task(upstream_to_browser()),
    }
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    for task in done:
        task.result()


def _voice_live_audio_event(audio: bytes) -> dict[str, str]:
    return {
        "type": "input_audio_buffer.append",
        "audio": base64.b64encode(audio).decode("ascii"),
    }


def _browser_voice_frame(
    payload: Any,
) -> tuple[Literal["json", "bytes"], dict[str, Any] | bytes] | None:
    if not isinstance(payload, dict):
        raise BackendError("Voice Live returned an invalid control event")
    event_type = payload.get("type")
    if event_type == "session.updated":
        session = payload.get("session")
        avatar = session.get("avatar") if isinstance(session, dict) else None
        ice_servers = avatar.get("ice_servers") if isinstance(avatar, dict) else []
        if not isinstance(ice_servers, list):
            raise BackendError("Voice Live returned invalid avatar ICE configuration")
        return (
            "json",
            {
                "type": "ready",
                "avatarEnabled": isinstance(avatar, dict),
                "iceServers": ice_servers,
            },
        )
    if event_type == "session.avatar.connecting":
        server_sdp = payload.get("server_sdp")
        if not isinstance(server_sdp, str) or not server_sdp:
            raise BackendError("Voice Live returned an invalid avatar answer")
        return ("json", {"type": "avatar_answer", "serverSdp": server_sdp})
    if event_type == "response.created":
        return ("json", {"type": "state", "state": "speaking"})
    if event_type == "response.done":
        return ("json", {"type": "state", "state": "listening"})
    if event_type == "response.audio.delta":
        encoded = payload.get("delta")
        if not isinstance(encoded, str):
            raise BackendError("Voice Live returned invalid audio data")
        try:
            return ("bytes", base64.b64decode(encoded, validate=True))
        except ValueError as exc:
            raise BackendError("Voice Live returned invalid audio data") from exc
    if event_type == "conversation.item.input_audio_transcription.completed":
        transcript = payload.get("transcript")
        if isinstance(transcript, str) and transcript:
            return ("json", {"type": "transcript", "role": "user", "text": transcript})
    if event_type == "response.audio_transcript.done":
        transcript = payload.get("transcript")
        if isinstance(transcript, str) and transcript:
            return ("json", {"type": "transcript", "role": "assistant", "text": transcript})
    if event_type == "error":
        error = payload.get("error")
        message = error.get("message") if isinstance(error, dict) else None
        return (
            "json",
            {
                "type": "error",
                "message": message if isinstance(message, str) else "Voice Live returned an error.",
            },
        )
    return None


def _voice_live_control_event(payload: Any) -> dict[str, str]:
    if not isinstance(payload, dict) or payload.get("type") != "avatar_connect":
        raise BackendError("The browser sent an invalid voice control event")
    client_sdp = payload.get("clientSdp")
    if not isinstance(client_sdp, str) or not client_sdp:
        raise BackendError("The avatar connection request is missing client SDP")
    return {"type": "session.avatar.connect", "client_sdp": client_sdp}


def _parse_voice_auth_frame(payload: Any) -> str:
    if not isinstance(payload, dict) or payload.get("type") != "auth":
        raise ValueError("The first WebSocket frame must be an auth message")
    handle = payload.get("sessionHandle")
    if not isinstance(handle, str) or not handle:
        raise ValueError("The auth frame must include a sessionHandle")
    return handle


def _parse_feedback(payload: Any) -> dict[str, str | int]:
    if not isinstance(payload, dict):
        raise RequestValidationError([])
    keys = set(payload)
    if keys == {"messageId", "sentiment"}:
        compatibility = CompatibilityFeedbackRequest.model_validate(payload)
        rating = 5 if compatibility.sentiment == "positive" else 1
        return {
            "message_id": compatibility.message_id,
            "sentiment": compatibility.sentiment,
            "rating": rating,
        }
    if keys.issubset({"callId", "rating", "comment"}) and {"callId", "rating"}.issubset(keys):
        legacy = LegacyFeedbackRequest.model_validate(payload)
        sentiment = "positive" if legacy.rating >= 4 else "negative"
        return {
            "message_id": legacy.call_id,
            "sentiment": sentiment,
            "rating": legacy.rating,
        }
    raise RequestValidationError([])


def _citation_response(citation: Citation) -> MessageCitationResponse:
    return MessageCitationResponse(id=citation.id, title=citation.title, url=citation.url)
