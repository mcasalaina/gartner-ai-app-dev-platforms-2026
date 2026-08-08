from __future__ import annotations

import logging
from dataclasses import dataclass
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .agent import BankServicingAgent
from .config import BridgeSettings
from .errors import BridgeError, ModeValidationError
from .foundry import FoundryBridgeClient
from .identity import AgentUserTokenValidator, LoopbackTokenBroker
from .telemetry import configure_telemetry

logger = logging.getLogger(__name__)
_ALLOWED_DEMO_MODES = {"service_discovery", "customer_servicing", "avatar_marketing"}


class RespondRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversation_id: str = Field(alias="conversationId", min_length=1)
    message: str = Field(min_length=1)


@dataclass(slots=True)
class BridgeServices:
    settings: BridgeSettings
    agent: BankServicingAgent


def create_app(
    settings: BridgeSettings,
    *,
    agent: BankServicingAgent | None = None,
) -> FastAPI:
    app = FastAPI(title="Bank Servicing Agent Bridge", version="0.1.0")
    app.state.services = BridgeServices(
        settings=settings,
        agent=agent
        or BankServicingAgent(
            token_broker=LoopbackTokenBroker(
                settings.identity,
                AgentUserTokenValidator(settings.identity),
            ),
            foundry_client=FoundryBridgeClient(settings.foundry),
        ),
    )

    @app.exception_handler(BridgeError)
    async def handle_bridge_error(_request: Request, exc: BridgeError) -> JSONResponse:
        return JSONResponse(
            {
                "detail": exc.message,
                "error": {"code": exc.error_code, "message": exc.message},
            },
            status_code=exc.status_code,
            headers={"Cache-Control": "no-store"},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled bridge failure", exc_info=exc)
        return JSONResponse(
            {
                "detail": "An unexpected error occurred.",
                "error": {"code": "internal_error", "message": "An unexpected error occurred."},
            },
            status_code=500,
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/respond")
    async def respond(
        body: RespondRequest,
        request: Request,
        traceparent: str | None = Header(default=None),
        tracestate: str | None = Header(default=None),
        baggage: str | None = Header(default=None),
        x_client_demo_mode: str | None = Header(default=None),
    ) -> JSONResponse:
        headers = {
            key: value
            for key, value in {
                "traceparent": traceparent,
                "tracestate": tracestate,
                "baggage": baggage,
                "x-client-demo-mode": x_client_demo_mode,
            }.items()
            if value
        }
        demo_mode = headers.get("x-client-demo-mode")
        if demo_mode and demo_mode not in _ALLOWED_DEMO_MODES:
            raise ModeValidationError(
                f"Unsupported x-client-demo-mode '{demo_mode}'. Expected one of: {', '.join(sorted(_ALLOWED_DEMO_MODES))}"
            )
        reply = await request.app.state.services.agent.respond(
            body.message,
            conversation_id=body.conversation_id,
            headers=headers,
        )
        logger.info(
            "bank_bridge_response mode=%s response_id=%s",
            demo_mode or "customer_servicing",
            reply.response_id,
        )
        return JSONResponse(
            {"text": reply.text, "responseId": reply.response_id},
            headers={"Cache-Control": "no-store", "x-agent-foundry-call-id": reply.response_id},
        )

    return app


def create_default_app() -> FastAPI:
    configure_telemetry()
    logging.basicConfig(level=logging.INFO)
    return create_app(BridgeSettings.from_environment())
