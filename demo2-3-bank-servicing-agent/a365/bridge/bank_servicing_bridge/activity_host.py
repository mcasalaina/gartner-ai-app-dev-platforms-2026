from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable

from aiohttp.web import Application, Request, Response, json_response, run_app
from aiohttp.web_middlewares import middleware
from microsoft_agents.activity import ChannelId
from microsoft_agents.authentication.msal import MsalConnectionManager
from microsoft_agents.hosting.aiohttp import (
    CloudAdapter,
    jwt_authorization_middleware,
    start_agent_process,
)
from microsoft_agents.hosting.core import (
    AgentApplication,
    AgentAuthConfiguration,
    Authorization,
    MemoryStorage,
    TurnContext,
    TurnState,
)
from microsoft_agents.activity import load_configuration_from_env
from microsoft_agents_a365.notifications.agent_notification import (
    AgentNotification,
    AgentNotificationActivity,
    NotificationTypes,
)

from .agent import BankServicingAgent
from .config import BridgeSettings
from .errors import BridgeError
from .foundry import FoundryBridgeClient
from .fee_dispute import requested_reply_cc
from .graph_mail import (
    AgentGraphMailResponder,
    AgentGraphMailSettings,
)
from .identity import AgentUserTokenValidator, LoopbackTokenBroker
from .telemetry import configure_telemetry

logger = logging.getLogger(__name__)


class Agent365ActivityHost:
    def __init__(self, settings: BridgeSettings) -> None:
        configuration = load_configuration_from_env(os.environ)
        self._settings = settings
        self._agent = BankServicingAgent(
            token_broker=LoopbackTokenBroker(
                settings.identity,
                AgentUserTokenValidator(settings.identity),
            ),
            foundry_client=FoundryBridgeClient(settings.foundry),
        )
        storage = MemoryStorage()
        connection_manager = MsalConnectionManager(**configuration)
        adapter = CloudAdapter(connection_manager=connection_manager)
        authorization = Authorization(storage, connection_manager, **configuration)
        self._app = AgentApplication[TurnState](
            storage=storage,
            adapter=adapter,
            authorization=authorization,
            **configuration,
        )
        self._adapter = adapter
        self._notifications = AgentNotification(self._app)
        self._mail_responder = AgentGraphMailResponder(
            AgentGraphMailSettings.from_environment(settings.identity)
        )
        self._identity_readiness = "disabled"
        self._readiness_task: asyncio.Task[None] | None = None
        self._register_handlers()

    def _register_handlers(self) -> None:
        async def welcome(context: TurnContext, _state: TurnState) -> None:
            await context.send_activity(
                "I'm Marco's Teller. I triage fee disputes from my own mailbox "
                "and require employee confirmation before any resolution handoff."
            )

        self._app.conversation_update("membersAdded")(welcome)
        self._app.message("/help")(welcome)

        @self._app.activity("message")
        async def on_message(context: TurnContext, _state: TurnState) -> None:
            try:
                notification = AgentNotificationActivity(context.activity)
            except ValueError:
                notification = None
            if (
                notification is not None
                and notification.notification_type == NotificationTypes.EMAIL_NOTIFICATION
            ):
                await self._handle_notification(context, notification)
                return
            channel_id = str(getattr(context.activity, "channel_id", "") or "")
            if "agent" in channel_id.casefold() and notification is not None:
                await self._handle_notification(
                    context,
                    notification,
                )
                return
            message = (context.activity.text or "").strip()
            if not message or message == "/help":
                return
            conversation_id = getattr(context.activity.conversation, "id", None) or "teams"
            try:
                reply = await self._agent.respond(
                    message,
                    conversation_id=f"teams:{conversation_id}",
                    headers={"x-client-demo-mode": "customer_servicing"},
                )
            except BridgeError as exc:
                logger.exception(
                    "agent365_message failed error_code=%s",
                    exc.error_code,
                )
                await context.send_activity(_safe_failure_message(exc))
                return
            logger.info("agent365_message response_id=%s", reply.response_id)
            await context.send_activity(reply.text)

        @self._notifications.on_agent_notification(
            channel_id=ChannelId(channel="agents", sub_channel="*")
        )
        async def on_notification(
            context: TurnContext,
            _state: TurnState,
            notification: AgentNotificationActivity,
        ) -> None:
            await self._handle_notification(context, notification)

    async def _handle_notification(
        self,
        context: TurnContext,
        notification: AgentNotificationActivity,
    ) -> None:
        if notification.notification_type != NotificationTypes.EMAIL_NOTIFICATION:
            await context.send_activity(
                "This agent currently handles fee-dispute email notifications."
            )
            return
        email = getattr(notification, "email", None)
        if email is None:
            await context.send_activity("The email notification contained no email details.")
            return
        body = getattr(email, "html_body", "") or getattr(email, "body", "")
        email_id = getattr(email, "id", None)
        if not email_id:
            await context.send_activity("The email notification contained no message ID.")
            return
        response_html, case_id = await self._agent.triage_email(
            body,
            conversation_id=f"email:{email_id}",
        )
        cc_recipients = requested_reply_cc(
            body,
            self._mail_responder.settings.reply_cc_allowlist,
        )
        logger.info(
            "agent365_email outcome=%s cc_count=%s",
            "triaged" if case_id else "blocked",
            len(cc_recipients),
        )
        await self._mail_responder.reply_to_message(
            message_id=email_id,
            html_body=response_html,
            cc_recipients=cc_recipients,
        )

    def create_web_app(self) -> Application:
        auth_config = _auth_configuration()

        async def entry_point(request: Request) -> Response:
            return await start_agent_process(request, self._app, self._adapter)

        async def health(_request: Request) -> Response:
            return json_response(
                {
                    "status": "ok",
                    "identityMode": "agent_user",
                    "identityReadiness": self._identity_readiness,
                    "agent": self._settings.foundry.agent_name,
                }
            )

        middlewares: list[Callable[[Request, Callable], Awaitable[Response]]] = []
        if auth_config:

            @middleware
            async def jwt_with_health_bypass(request: Request, handler: Callable) -> Response:
                if request.path in {"/health", "/api/health"}:
                    return await handler(request)
                return await jwt_authorization_middleware(request, handler)

            middlewares.append(jwt_with_health_bypass)

        app = Application(middlewares=middlewares)
        app["agent_configuration"] = auth_config
        app["agent_app"] = self._app
        app["adapter"] = self._adapter
        app.router.add_post("/api/messages", entry_point)
        app.router.add_get("/api/messages", lambda _request: Response(status=200))
        app.router.add_get("/health", health)
        app.router.add_get("/api/health", health)
        app.on_startup.append(self._start_identity_readiness)
        return app

    async def _start_identity_readiness(self, _app: Application) -> None:
        if os.getenv("BRIDGE_IDENTITY_SMOKE_ENABLED", "").casefold() != "true":
            return
        self._identity_readiness = "pending"
        self._readiness_task = asyncio.create_task(self._run_identity_readiness())

    async def _run_identity_readiness(self) -> None:
        try:
            _response_html, case_id = await self._agent.triage_email(
                "I'm Maria Garcia. Please review a disputed $35 ATM fee on my checking "
                "account ending in 1013, explain whether it qualifies for a refund, and "
                "tell me whether an employee must approve it.",
                conversation_id="readiness",
            )
            if case_id is None:
                raise RuntimeError("Readiness intake was blocked")
            self._identity_readiness = "ready"
            logger.info("agent365_identity_smoke status=ready")
        except Exception:
            self._identity_readiness = "failed"
            logger.exception("agent365_identity_smoke status=failed")


def _auth_configuration() -> AgentAuthConfiguration | None:
    client_id = os.getenv("CLIENT_ID")
    tenant_id = os.getenv("TENANT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    if not all((client_id, tenant_id, client_secret)):
        logger.warning("Agent 365 inbound authentication is not configured")
        return None
    return AgentAuthConfiguration(
        client_id=client_id,
        tenant_id=tenant_id,
        client_secret=client_secret,
        scopes=["5a807f24-c9de-44ee-a3a7-329e88a00ffc/.default"],
    )


def _safe_failure_message(error: BridgeError) -> str:
    return (
        "I couldn't confirm the bank-servicing result "
        f"({error.error_code}). The request was not retried automatically. "
        "If this included an email send, check Sent Items before retrying."
    )


def main() -> None:
    configure_telemetry()
    logging.basicConfig(level=logging.INFO)
    settings = BridgeSettings.from_environment()
    host = Agent365ActivityHost(settings)
    run_app(
        host.create_web_app(),
        host=settings.host,
        port=settings.port,
        handle_signals=True,
    )


if __name__ == "__main__":
    main()
