from __future__ import annotations

import asyncio
import os

from azure.ai.agentserver.responses import (
    CreateResponse,
    ResponseContext,
    ResponsesAgentServerHost,
    ResponsesServerOptions,
    TextResponse,
)

from bank_servicing_agent.agent_context import (
    reset_platform_user_id,
    set_platform_user_id,
)
from bank_servicing_agent.config import Settings
from bank_servicing_agent.foundry_backend import FoundryGenerationBackend
from bank_servicing_agent.history import extract_conversation_turns, split_latest_user_turn
from bank_servicing_agent.instructions_loader import load_runtime_instructions
from bank_servicing_agent.logging_utils import configure_logging
from bank_servicing_agent.models import BankServicingRequest
from bank_servicing_agent.modes import DemoModeError, resolve_demo_mode
from bank_servicing_agent.orchestrator import BankServicingOrchestrator


class BankServicingResponseHost(ResponsesAgentServerHost):
    def __init__(self, orchestrator: BankServicingOrchestrator, logger) -> None:
        super().__init__(options=ResponsesServerOptions(default_fetch_history_count=12))
        self._orchestrator = orchestrator
        self._logger = logger
        self.response_handler(self._handle_response)

    async def _handle_response(
        self,
        request: CreateResponse,
        context: ResponseContext,
        cancellation_signal: asyncio.Event,
    ) -> TextResponse:
        del cancellation_signal
        try:
            mode = resolve_demo_mode(context.client_headers)
        except DemoModeError as exc:
            self._logger.info(
                "bank_request decision=invalid_mode call_id=%s user_id=%s",
                "present" if context.platform_context.call_id else "missing",
                "present" if context.platform_context.user_id_key else "missing",
            )
            return TextResponse(context, request, text=str(exc))

        input_items = await context.get_input_items()
        user_text, input_history = split_latest_user_turn(input_items)
        if not user_text:
            user_text = await context.get_input_text()
        history_items = await context.get_history()
        platform_history = extract_conversation_turns(history_items)
        history = input_history if input_history else platform_history
        agent_request = BankServicingRequest(
            mode=mode,
            user_text=user_text,
            history=history,
            conversation_id=context.conversation_id,
            call_id=context.platform_context.call_id,
            user_id=context.platform_context.user_id_key,
        )
        user_context_token = set_platform_user_id(
            context.platform_context.user_id_key
        )
        try:
            agent_response = await self._orchestrator.handle(agent_request)
        finally:
            reset_platform_user_id(user_context_token)
        self._logger.info(
            "bank_request decision=%s mode=%s blocked=%s repaired=%s issues=%s call_id=%s user_id=%s",
            agent_response.metadata.get("decision"),
            mode.value,
            agent_response.blocked,
            agent_response.repaired,
            ",".join(agent_response.metadata.get("issues", ())),
            "present" if context.platform_context.call_id else "missing",
            "present" if context.platform_context.user_id_key else "missing",
        )
        return TextResponse(context, request, text=agent_response.text)



def build_app() -> BankServicingResponseHost:
    settings = Settings.from_environment()
    os.environ.setdefault("FOUNDRY_PROJECT_ENDPOINT", settings.project_endpoint)
    logger = configure_logging(settings.log_level)
    instructions = load_runtime_instructions(settings.instructions_path)
    backend = FoundryGenerationBackend(settings)
    orchestrator = BankServicingOrchestrator(
        instructions=instructions,
        backend=backend,
        email_sender=backend,
        agent365_user_id=(
            settings.agent365_work_iq.agent_user_id
            if settings.agent365_work_iq
            else None
        ),
    )
    return BankServicingResponseHost(orchestrator, logger)



def main() -> None:
    app = build_app()
    app.run()
