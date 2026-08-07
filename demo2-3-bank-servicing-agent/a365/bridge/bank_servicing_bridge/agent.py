from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

import httpx

from .errors import UpstreamError
from .foundry import BridgeResponse, FoundryBridgeClient, Message
from .fee_dispute import (
    FeeDisputeCase,
    build_confirmation_prompt,
    build_triage_prompt,
    contains_unsafe_completion_claim,
    fee_dispute_case_id,
    grounded_customer_response,
    inspect_fee_dispute_email,
    parse_case_command,
    rejected_email_response,
)
from .identity import LoopbackTokenBroker


@dataclass(slots=True)
class BankServicingAgent:
    token_broker: LoopbackTokenBroker
    foundry_client: FoundryBridgeClient
    histories: dict[str, list[Message]] = field(default_factory=dict)
    fee_disputes: dict[str, FeeDisputeCase] = field(default_factory=dict)

    async def respond(
        self,
        message: str,
        *,
        conversation_id: str,
        headers: Mapping[str, str] | None = None,
    ) -> BridgeResponse:
        command = parse_case_command(message)
        if command:
            return await self._handle_case_command(
                *command,
                conversation_id=conversation_id,
                headers=headers,
            )
        return await self._respond_foundry(
            message,
            conversation_id=conversation_id,
            headers=headers,
        )

    async def triage_email(
        self,
        raw_body: str,
        *,
        conversation_id: str,
    ) -> tuple[str, str | None]:
        intake = inspect_fee_dispute_email(raw_body)
        if not intake.allowed:
            return rejected_email_response(intake.code), None

        case_id = fee_dispute_case_id(intake.safe_text)
        case = self.fee_disputes.get(case_id)
        if case is None:
            case = FeeDisputeCase(
                case_id=case_id,
                conversation_id=conversation_id,
                status="pending_employee_confirmation",
            )
            self.fee_disputes[case_id] = case
            triage = await self._respond_foundry(
                build_triage_prompt(case_id, intake.safe_text),
                conversation_id=f"email:{case_id}",
                headers={"x-client-demo-mode": "customer_servicing"},
            )
            case.triage_text = triage.text
            case.triage_response_id = triage.response_id
        return grounded_customer_response(case_id, case.triage_text), case_id

    async def _handle_case_command(
        self,
        action: str,
        case_id: str,
        *,
        conversation_id: str,
        headers: Mapping[str, str] | None,
    ) -> BridgeResponse:
        case = self.fee_disputes.get(case_id)
        if case is None:
            return BridgeResponse(
                response_id=f"local-{case_id.casefold()}",
                text=f"Fee dispute {case_id} was not found in this bridge instance.",
            )
        if action == "review":
            return BridgeResponse(
                response_id=case.triage_response_id,
                text=(
                    f"Fee dispute {case_id} is pending employee confirmation.\n\n"
                    f"{case.triage_text}\n\n"
                    f"To proceed safely, use: confirm fee dispute {case_id} "
                    f"or escalate fee dispute {case_id}."
                ),
            )
        case.status = f"employee_{action}ed"
        response = await self._respond_foundry(
            build_confirmation_prompt(case, action),
            conversation_id=conversation_id,
            headers=headers or {"x-client-demo-mode": "customer_servicing"},
        )
        if contains_unsafe_completion_claim(response.text):
            return BridgeResponse(
                response_id=response.response_id,
                text=(
                    f"Fee dispute {case_id} was handed off after employee {action}. "
                    "No fee change was executed. Use the approved bank servicing "
                    "system to complete the action, then send the customer-ready response."
                ),
            )
        return response

    async def _respond_foundry(
        self,
        message: str,
        *,
        conversation_id: str,
        headers: Mapping[str, str] | None = None,
    ) -> BridgeResponse:
        identity = await self.token_broker.acquire()
        history = self.histories.setdefault(conversation_id, [])
        history.append(Message(role="user", content=message))
        try:
            reply = await self.foundry_client.respond(
                bearer_token=identity.token,
                messages=history,
                headers=dict(headers or {}),
            )
        except httpx.TimeoutException as exc:
            history.pop()
            raise UpstreamError("Foundry agent request timed out") from exc
        except httpx.RequestError as exc:
            history.pop()
            raise UpstreamError("Foundry agent request failed") from exc
        except BaseException:
            history.pop()
            raise
        history.append(Message(role="assistant", content=reply.text))
        return reply
