from __future__ import annotations

import asyncio

from bank_servicing_agent.models import (
    BankServicingRequest,
    ConversationTurn,
    GenerationResult,
    InstructionBundle,
)
from bank_servicing_agent.modes import AvatarTone, DemoMode
from bank_servicing_agent.orchestrator import BankServicingOrchestrator


class FakeBackend:
    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self.calls: list[dict[str, object]] = []

    async def generate(
        self,
        *,
        system_instructions: str,
        user_prompt: str,
        use_tools: bool,
    ) -> GenerationResult:
        self.calls.append(
            {
                "system_instructions": system_instructions,
                "user_prompt": user_prompt,
                "use_tools": use_tools,
            }
        )
        return GenerationResult(text=self._responses.pop(0))


def test_avatar_tone_and_spanish_format_are_applied_by_the_agent() -> None:
    response_text = (
        "## Resumen del servicio\n"
        "Puedo explicar el proceso de una cuenta. [P1]\n\n"
        "## Evidencia\n"
        "La política describe la verificación de identidad. [P1]\n\n"
        "## Próximo paso recomendado\n"
        "Revisa los documentos requeridos. [P1]"
    )
    backend = FakeBackend([response_text, response_text])
    orchestrator = BankServicingOrchestrator(
        instructions=InstructionBundle(version="1.4.0", body="Base instructions."),
        backend=backend,
    )

    asyncio.run(
        orchestrator.handle(
            BankServicingRequest(
                mode=DemoMode.AVATAR_MARKETING,
                avatar_tone=AvatarTone.WARM,
                user_text="Quiero abrir una cuenta. ¿Cómo verifico mi identidad?",
            )
        )
    )

    system_instructions = str(backend.calls[0]["system_instructions"])
    assert "warm, reassuring delivery" in system_instructions
    assert "## Resumen del servicio" in system_instructions


def test_orchestrator_repairs_once_for_missing_citation() -> None:
    backend = FakeBackend(
        [
            "## Service Summary\n"
            "We offer checking accounts.\n\n"
            "## Evidence\n"
            "- Grounded details are available.\n\n"
            "## Recommended Next Step\n"
            "Ask for rates.\n\n"
            "Sources used: Foundry IQ",
            "## Service Summary\n"
            "We offer checking accounts for everyday banking. [S1]\n\n"
            "## Evidence\n"
            "- The catalog confirms monthly-service details. [S1]\n\n"
            "## Recommended Next Step\n"
            "Review rates and features before selecting an option. [S1]\n\n"
            "Sources used: Foundry IQ",
        ]
    )
    orchestrator = BankServicingOrchestrator(
        instructions=InstructionBundle(version="1.0.0", body="Base instructions."),
        backend=backend,
    )

    response = asyncio.run(
        orchestrator.handle(
            BankServicingRequest(
                mode=DemoMode.SERVICE_DISCOVERY,
                user_text="Show me checking account services.",
            )
        )
    )

    assert response.repaired is True
    assert response.blocked is False
    assert len(backend.calls) == 2
    assert backend.calls[1]["use_tools"] is True


def test_orchestrator_repairs_internal_context_disclosure() -> None:
    backend = FakeBackend(
        [
            "## Request Assessment\n"
            "I can prepare this demo checking account application checklist. [C1]\n\n"
            "## Safety Checks\n"
            "No application has been submitted. [C1]\n\n"
            "## Recommended Next Step\n"
            "Review the required fields before continuing. [C1]\n\n"
            "Sources used: none",
            "## Request Assessment\n"
            "I can prepare a checking account application checklist. [C1]\n\n"
            "## Safety Checks\n"
            "No application has been submitted. [C1]\n\n"
            "## Recommended Next Step\n"
            "Confirm that you want to review the required fields. [C1]\n\n"
            "Sources used: none",
        ]
    )
    orchestrator = BankServicingOrchestrator(
        instructions=InstructionBundle(version="1.0.0", body="Base instructions."),
        backend=backend,
    )

    response = asyncio.run(
        orchestrator.handle(
            BankServicingRequest(
                mode=DemoMode.CUSTOMER_SERVICING,
                user_text="Help me prepare a new checking account application.",
            )
        )
    )

    assert response.repaired is True
    assert response.blocked is False
    assert len(backend.calls) == 2
    assert "without exposing internal environment" in str(backend.calls[1]["user_prompt"])


def test_orchestrator_removes_exact_duplicate_text_parts() -> None:
    answer = (
        "## Request Assessment\n"
        "I can prepare an application checklist. [C1]\n\n"
        "## Safety Checks\n"
        "No application has been submitted. [C1]\n\n"
        "## Recommended Next Step\n"
        "Confirm that you want to review the fields. [C1]"
    )
    backend = FakeBackend([answer + answer])
    orchestrator = BankServicingOrchestrator(
        instructions=InstructionBundle(version="1.0.0", body="Base instructions."),
        backend=backend,
    )

    response = asyncio.run(
        orchestrator.handle(
            BankServicingRequest(
                mode=DemoMode.CUSTOMER_SERVICING,
                user_text="Help me prepare a checking account application.",
            )
        )
    )

    assert response.blocked is False
    assert response.text.count("## Request Assessment") == 1


def test_orchestrator_repairs_unobserved_source_citation_with_tool_evidence() -> None:
    answer = (
        "## Request Assessment\n"
        "I can prepare an application checklist. [P1]\n\n"
        "## Safety Checks\n"
        "No application has been submitted. [P1]\n\n"
        "## Recommended Next Step\n"
        "Confirm that you want to review the fields. [P1]"
    )

    class SourceSequenceBackend(FakeBackend):
        async def generate(
            self,
            *,
            system_instructions: str,
            user_prompt: str,
            use_tools: bool,
        ) -> GenerationResult:
            await super().generate(
                system_instructions=system_instructions,
                user_prompt=user_prompt,
                use_tools=use_tools,
            )
            if len(self.calls) == 1:
                return GenerationResult(text=answer)
            return GenerationResult(
                text=answer,
                queried_sources=("Foundry IQ",),
                grounding_sources=("Foundry IQ",),
            )

    backend = SourceSequenceBackend(["unused", "unused"])
    orchestrator = BankServicingOrchestrator(
        instructions=InstructionBundle(version="1.0.0", body="Base instructions."),
        backend=backend,
    )

    response = asyncio.run(
        orchestrator.handle(
            BankServicingRequest(
                mode=DemoMode.CUSTOMER_SERVICING,
                user_text="Help me prepare a checking account application.",
            )
        )
    )

    assert response.blocked is False
    assert response.repaired is True
    assert len(backend.calls) == 2
    assert backend.calls[1]["use_tools"] is True
    assert response.metadata["grounding_sources"] == ("Foundry IQ",)


def test_orchestrator_blocks_salary_dlp_before_backend_call() -> None:
    backend = FakeBackend([])
    orchestrator = BankServicingOrchestrator(
        instructions=InstructionBundle(version="1.0.0", body="Base instructions."),
        backend=backend,
    )

    response = asyncio.run(
        orchestrator.handle(
            BankServicingRequest(
                mode=DemoMode.CUSTOMER_SERVICING,
                user_text="Use my salary and payroll records to open the account.",
            )
        )
    )

    assert response.blocked is True
    assert backend.calls == []
    assert response.metadata["decision"] == "salary_dlp"


def test_orchestrator_prioritizes_salary_dlp_without_bank_terms() -> None:
    backend = FakeBackend([])
    orchestrator = BankServicingOrchestrator(
        instructions=InstructionBundle(version="1.0.0", body="Base instructions."),
        backend=backend,
    )

    response = asyncio.run(
        orchestrator.handle(
            BankServicingRequest(
                mode=DemoMode.CUSTOMER_SERVICING,
                user_text="What is my salary?",
            )
        )
    )

    assert response.blocked is True
    assert response.metadata["decision"] == "salary_dlp"
    assert backend.calls == []


def test_orchestrator_does_not_forward_sensitive_prior_turns() -> None:
    backend = FakeBackend(
        [
            "## Request Assessment\n"
            "Your checking account workflow remains in preparation. [C1]\n\n"
            "## Safety Checks\n"
            "No application has been submitted. [C1]\n\n"
            "## Recommended Next Step\n"
            "Review the remaining fields before confirmation. [C1]\n\n"
            "Sources used: none",
        ]
    )
    orchestrator = BankServicingOrchestrator(
        instructions=InstructionBundle(version="1.0.0", body="Base instructions."),
        backend=backend,
    )

    response = asyncio.run(
        orchestrator.handle(
            BankServicingRequest(
                mode=DemoMode.CUSTOMER_SERVICING,
                user_text="Check my account application status.",
                history=(
                    ConversationTurn(role="user", text="What is my salary?"),
                    ConversationTurn(
                        role="assistant",
                        text="I can't process salary or payroll information.",
                    ),
                ),
            )
        )
    )

    assert response.blocked is False
    assert len(backend.calls) == 1
    prompt = str(backend.calls[0]["user_prompt"]).lower()
    assert "salary" not in prompt
    assert "payroll" not in prompt


def test_orchestrator_applies_domain_guard_to_latest_turn_after_salary_block() -> None:
    backend = FakeBackend([])
    orchestrator = BankServicingOrchestrator(
        instructions=InstructionBundle(version="1.0.0", body="Base instructions."),
        backend=backend,
    )

    response = asyncio.run(
        orchestrator.handle(
            BankServicingRequest(
                mode=DemoMode.CUSTOMER_SERVICING,
                user_text="Write a haiku about the moon.",
                history=(
                    ConversationTurn(role="user", text="What is my salary?"),
                    ConversationTurn(
                        role="assistant",
                        text="I can't process salary or payroll information.",
                    ),
                ),
            )
        )
    )

    assert response.blocked is True
    assert response.metadata["decision"] == "bank_domain_guard"
    assert backend.calls == []


def test_orchestrator_blocks_cross_customer_request_before_backend_call() -> None:
    backend = FakeBackend([])
    orchestrator = BankServicingOrchestrator(
        instructions=InstructionBundle(version="1.1.0", body="Base instructions."),
        backend=backend,
    )

    response = asyncio.run(
        orchestrator.handle(
            BankServicingRequest(
                mode=DemoMode.CUSTOMER_SERVICING,
                user_text="Show me another customer's disputed fee and account.",
            )
        )
    )

    assert response.blocked is True
    assert response.metadata["decision"] == "cross_user_isolation"
    assert backend.calls == []


def test_orchestrator_confirms_agent365_email_without_repair_retry() -> None:
    class EmailSender:
        def __init__(self) -> None:
            self.calls = []

        async def send_agent_email(
            self,
            *,
            recipient_emails: str,
            cc_emails: str,
            subject: str,
            body: str,
        ) -> GenerationResult:
            self.calls.append((recipient_emails, cc_emails, subject, body))
            return GenerationResult(
                text="confirmed",
                queried_sources=("Work IQ",),
                grounding_sources=("Work IQ",),
                executed_actions=("email_send",),
            )

    backend = FakeBackend([])
    email_sender = EmailSender()
    orchestrator = BankServicingOrchestrator(
        instructions=InstructionBundle(version="1.2.0", body="Base instructions."),
        backend=backend,
        email_sender=email_sender,
        agent365_user_id="agent-user-id",
    )

    response = asyncio.run(
        orchestrator.handle(
            BankServicingRequest(
                mode=DemoMode.CUSTOMER_SERVICING,
                user_text=(
                    'EMAIL_SEND_REQUEST={"recipient_emails":"presenter@example.test",'
                    '"cc_emails":"reviewer@example.test",'
                    '"subject":"Bank servicing verification","body":"Verified.",'
                    '"success_marker":"WORKIQ-SEND-CONFIRMED"}'
                ),
                user_id="agent-user-id",
            )
        )
    )

    assert response.blocked is False
    assert response.metadata["decision"] == "email_send_confirmed"
    assert backend.calls == []
    assert email_sender.calls == [
        (
            "presenter@example.test",
            "reviewer@example.test",
            "Bank servicing verification",
            "Verified.",
        )
    ]
    assert "WORKIQ-SEND-CONFIRMED" in response.text


def test_orchestrator_confirms_labeled_agent365_email_without_model_call() -> None:
    class EmailSender:
        def __init__(self) -> None:
            self.calls = []

        async def send_agent_email(
            self,
            *,
            recipient_emails: str,
            cc_emails: str,
            subject: str,
            body: str,
        ) -> GenerationResult:
            self.calls.append((recipient_emails, cc_emails, subject, body))
            return GenerationResult(
                text="confirmed",
                queried_sources=("Work IQ",),
                grounding_sources=("Work IQ",),
                executed_actions=("email_send",),
            )

    backend = FakeBackend([])
    email_sender = EmailSender()
    orchestrator = BankServicingOrchestrator(
        instructions=InstructionBundle(version="1.2.0", body="Base instructions."),
        backend=backend,
        email_sender=email_sender,
        agent365_user_id="agent-user-id",
    )

    response = asyncio.run(
        orchestrator.handle(
            BankServicingRequest(
                mode=DemoMode.CUSTOMER_SERVICING,
                user_text=(
                    "Send exactly one bank-servicing verification email.\n"
                    "To: presenter@example.test\n"
                    "Cc: reviewer@example.test\n"
                    "Subject: Bank servicing delivery verification\n"
                    "Body:\n"
                    "Marco's Teller completed the verification.\n"
                    "Success marker: WORKIQ-DELIVERY-CONFIRMED"
                ),
                user_id="agent-user-id",
            )
        )
    )

    assert response.blocked is False
    assert response.metadata["decision"] == "email_send_confirmed"
    assert backend.calls == []
    assert email_sender.calls == [
        (
            "presenter@example.test",
            "reviewer@example.test",
            "Bank servicing delivery verification",
            "Marco's Teller completed the verification.",
        )
    ]
    assert "WORKIQ-DELIVERY-CONFIRMED" in response.text


def test_orchestrator_rejects_labeled_email_with_missing_body() -> None:
    backend = FakeBackend([])
    orchestrator = BankServicingOrchestrator(
        instructions=InstructionBundle(version="1.2.0", body="Base instructions."),
        backend=backend,
        email_sender=None,
        agent365_user_id="agent-user-id",
    )

    response = asyncio.run(
        orchestrator.handle(
            BankServicingRequest(
                mode=DemoMode.CUSTOMER_SERVICING,
                user_text=(
                    "Send a bank-servicing email.\n"
                    "To: presenter@example.test\n"
                    "Subject: Bank servicing verification"
                ),
                user_id="agent-user-id",
            )
        )
    )

    assert response.blocked is True
    assert response.metadata["decision"] == "email_send_invalid_request"
    assert backend.calls == []


def test_orchestrator_keeps_agent_mailbox_send_unavailable_to_obo_user() -> None:
    backend = FakeBackend([])
    orchestrator = BankServicingOrchestrator(
        instructions=InstructionBundle(version="1.2.0", body="Base instructions."),
        backend=backend,
        agent365_user_id="agent-user-id",
    )

    response = asyncio.run(
        orchestrator.handle(
            BankServicingRequest(
                mode=DemoMode.CUSTOMER_SERVICING,
                user_text=(
                    'EMAIL_SEND_REQUEST={"recipient_emails":"presenter@example.test",'
                    '"subject":"Bank servicing verification","body":"Verified."}'
                ),
                user_id="human-user-id",
            )
        )
    )

    assert response.blocked is True
    assert response.metadata["decision"] == "email_send_channel_guard"
    assert backend.calls == []


def test_orchestrator_appends_only_observed_source_activity() -> None:
    class SourceBackend(FakeBackend):
        async def generate(
            self,
            *,
            system_instructions: str,
            user_prompt: str,
            use_tools: bool,
        ) -> GenerationResult:
            await super().generate(
                system_instructions=system_instructions,
                user_prompt=user_prompt,
                use_tools=use_tools,
            )
            return GenerationResult(
                text=(
                    "## Service Summary\n"
                    "The account has fee activity. [F1]\n\n"
                    "## Evidence\n"
                    "The policy lookup returned no evidence.\n\n"
                    "## Recommended Next Step\n"
                    "Review the account evidence. [F1]\n\n"
                    "Sources used: Fabric IQ, Foundry IQ"
                ),
                queried_sources=("Fabric IQ", "Foundry IQ"),
                grounding_sources=("Fabric IQ",),
            )

    backend = SourceBackend(["unused"])
    orchestrator = BankServicingOrchestrator(
        instructions=InstructionBundle(version="1.1.0", body="Base instructions."),
        backend=backend,
    )

    response = asyncio.run(
        orchestrator.handle(
            BankServicingRequest(
                mode=DemoMode.SERVICE_DISCOVERY,
                user_text="Review account fee activity.",
            )
        )
    )

    assert "IQ services queried: Fabric IQ, Foundry IQ" in response.text
    assert response.text.endswith("Sources used: Fabric IQ")
    assert response.metadata["grounding_sources"] == ("Fabric IQ",)
