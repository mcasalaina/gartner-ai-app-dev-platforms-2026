from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from bank_servicing_agent.modes import DemoMode


@dataclass(frozen=True, slots=True)
class ConversationTurn:
    role: str
    text: str


@dataclass(frozen=True, slots=True)
class InstructionBundle:
    version: str
    body: str


@dataclass(frozen=True, slots=True)
class BankServicingRequest:
    mode: DemoMode
    user_text: str
    history: tuple[ConversationTurn, ...] = ()
    conversation_id: str | None = None
    call_id: str | None = None
    user_id: str | None = None


@dataclass(frozen=True, slots=True)
class BankServicingResponse:
    text: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    blocked: bool = False
    repaired: bool = False


@dataclass(frozen=True, slots=True)
class GenerationResult:
    text: str
    queried_sources: tuple[str, ...] = ()
    grounding_sources: tuple[str, ...] = ()
    executed_actions: tuple[str, ...] = ()


class TextGenerationBackend(Protocol):
    async def generate(
        self,
        *,
        system_instructions: str,
        user_prompt: str,
        use_tools: bool,
    ) -> GenerationResult: ...


class AgentEmailSender(Protocol):
    async def send_agent_email(
        self,
        *,
        recipient_emails: str,
        cc_emails: str,
        subject: str,
        body: str,
    ) -> GenerationResult: ...
