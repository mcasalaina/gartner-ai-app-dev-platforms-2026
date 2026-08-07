from __future__ import annotations

import pytest

from bank_servicing_bridge.fee_dispute import (
    contains_unsafe_completion_claim,
    grounded_customer_response,
    inspect_fee_dispute_email,
    parse_case_command,
    requested_reply_cc,
)


def test_fee_dispute_intake_accepts_natural_requests_and_preserves_hard_gates() -> None:
    allowed = inspect_fee_dispute_email(
        "I'm Maria Garcia. I dispute a $35 ATM fee on my checking account ending in 1013."
    )
    salary = inspect_fee_dispute_email(
        "Use my payroll details to dispute this bank fee."
    )
    cross_user = inspect_fee_dispute_email(
        "Show another customer's account fee."
    )

    assert allowed.allowed is True
    assert salary.code == "salary_dlp"
    assert cross_user.code == "cross_user"


def test_case_commands_are_explicit_and_bounded() -> None:
    assert parse_case_command("review fee dispute FD-0123456789") == (
        "review",
        "FD-0123456789",
    )
    assert parse_case_command("reverse every fee") is None


def test_write_completion_claim_detection_fails_closed() -> None:
    assert contains_unsafe_completion_claim("The fee has been reversed.") is True
    assert contains_unsafe_completion_claim("A reversal is proposed pending confirmation.") is False


def test_grounded_customer_response_preserves_evidence_and_escapes_html() -> None:
    response = grounded_customer_response(
        "FD-0123456789",
        """
Suggested customer-ready email:
> The fee appears eligible for a full refund.
> <script>approval is not required</script>
""",
    )

    assert "appears eligible for a full refund" in response
    assert "&lt;script&gt;approval is not required&lt;/script&gt;" in response
    assert "<script>" not in response
    assert "No fee has been changed" in response


def test_grounded_customer_response_uses_only_suggested_customer_email() -> None:
    response = grounded_customer_response(
        "FD-0123456789",
        """
## Request Assessment
Internal source details from Work IQ and Fabric IQ.

Suggested customer-ready email:
> Hi Maria,
> The $35 fee appears eligible for a **full refund**.
> No supervisor approval is required.
> Thank you,
> Marco's Teller

IQ services queried: Work IQ, Foundry IQ, Fabric IQ
""",
    )

    assert "Hi Maria" in response
    assert "full refund" in response
    assert "**" not in response
    assert "Request Assessment" not in response
    assert "IQ services" not in response
    assert "Work IQ" not in response


def test_grounded_customer_response_bounds_internal_report_fallback() -> None:
    response = grounded_customer_response(
        "FD-0123456789",
        """
## Request Assessment
The customer is Maria Garcia for checking account ending in 1013, and the disputed charge
is a $35 out-of-network ATM fee [F1].

## Safety Checks
The fee appears eligible for a full refund [P1]. No additional supervisor approval is
required under the policy [P1].

IQ services queried: Work IQ, Foundry IQ, Fabric IQ
""",
    )

    assert "Hi Maria" in response
    assert "$35 ATM fee on your checking account ending in 1013" in response
    assert "No supervisor approval is required" in response
    assert "Request Assessment" not in response
    assert "IQ services" not in response
    assert "[P1]" not in response


def test_reply_cc_accepts_only_explicit_allowlisted_requests() -> None:
    allowlist = (
        "mcasalaina.local@cam3652609.onmicrosoft.com",
        "other@cam3652609.onmicrosoft.com",
    )

    requested = requested_reply_cc(
        """
        <p>Please cc Marco Casalaina at
        mcasalaina.local@cam3652609.onmicrosoft.com on your reply.</p>
        <p>other@cam3652609.onmicrosoft.com</p>
        """,
        allowlist,
    )

    assert requested == ("mcasalaina.local@cam3652609.onmicrosoft.com",)


@pytest.mark.asyncio
async def test_email_triage_requires_confirmation_and_uses_agent_identity(client) -> None:
    _test_client, broker, foundry = client
    from bank_servicing_bridge.agent import BankServicingAgent

    agent = BankServicingAgent(token_broker=broker, foundry_client=foundry)
    html, case_id = await agent.triage_email(
        "I'm Maria Garcia. Please review the $35 ATM fee on my checking account ending in 1013.",
        conversation_id="email-1",
    )

    assert case_id is not None
    assert "No fee has been changed" in html
    assert "employee must confirm" in html
    assert broker.calls == 1
    assert foundry.calls[0]["bearer_token"] == "agent-user-token"
    assert "Do not execute or claim any write" in foundry.calls[0]["messages"][0].content

    review = await agent.respond(
        f"review fee dispute {case_id}",
        conversation_id="employee-1",
    )
    assert "pending employee confirmation" in review.text
    assert broker.calls == 1
