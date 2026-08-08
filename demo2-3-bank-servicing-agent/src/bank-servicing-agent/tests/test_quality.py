from __future__ import annotations

from bank_servicing_agent.dlp import evaluate_salary_dlp, evaluate_salary_output_dlp
from bank_servicing_agent.kyc_state import SyntheticKycState
from bank_servicing_agent.modes import DemoMode
from bank_servicing_agent.quality import evaluate_response_quality


def test_quality_accepts_cited_service_discovery_response() -> None:
    assessment = evaluate_response_quality(
        DemoMode.SERVICE_DISCOVERY,
        "Show me checking account services.",
        "## Service Summary\n"
        "Checking account options are available for everyday banking. [S1]\n\n"
        "## Evidence\n"
        "- Account access and fees were grounded from the service catalog. [S1]\n\n"
        "## Recommended Next Step\n"
        "Compare the monthly fee and ATM coverage before choosing. [S1]\n\n"
        "Sources used: Foundry IQ",
        SyntheticKycState(False, False, False),
    )

    assert assessment.passed is True


def test_quality_accepts_cited_spanish_avatar_response() -> None:
    assessment = evaluate_response_quality(
        DemoMode.AVATAR_MARKETING,
        "Quiero abrir una cuenta. ¿Cómo verifico mi identidad?",
        "## Resumen del servicio\n"
        "Puedo explicar el proceso de una cuenta sin enviar una solicitud. [P1]\n\n"
        "## Evidencia\n"
        "La política describe los pasos de verificación de identidad. [P1]\n\n"
        "## Próximo paso recomendado\n"
        "Revisa los documentos requeridos antes de continuar. [P1]",
        SyntheticKycState(True, False, False),
    )

    assert assessment.passed is True


def test_quality_rejects_unsafe_account_opening_claim() -> None:
    assessment = evaluate_response_quality(
        DemoMode.CUSTOMER_SERVICING,
        "Help me open a checking account.",
        "## Request Assessment\n"
        "Your account is now open. [C1]\n\n"
        "## Safety Checks\n"
        "The application was reviewed. [C1]\n\n"
        "## Recommended Next Step\n"
        "You're all set. [C1]",
        SyntheticKycState(True, True, False),
    )

    assert assessment.passed is False
    assert any(issue.code == "unsafe_completion_claim" for issue in assessment.issues)


def test_quality_allows_negated_completion_disclaimer() -> None:
    assessment = evaluate_response_quality(
        DemoMode.CUSTOMER_SERVICING,
        "Help me open a checking account.",
        "## Request Assessment\n"
        "I can guide a checking account application. [C1]\n\n"
        "## Safety Checks\n"
        "I should not claim the application is submitted or approved. [C1]\n\n"
        "## Recommended Next Step\n"
        "Confirm that you want to review the application fields. [C1]\n\n"
        "Sources used: none",
        SyntheticKycState(True, False, False),
    )

    assert assessment.passed is True


def test_quality_allows_conditional_open_account_policy_language() -> None:
    assessment = evaluate_response_quality(
        DemoMode.CUSTOMER_SERVICING,
        "Explain whether this ATM fee qualifies for reversal.",
        "## Request Assessment\n"
        "The $35 ATM fee is eligible for policy review. [F1]\n\n"
        "## Safety Checks\n"
        "The policy path applies assuming the account is open and in good "
        "standing. [P1]\n\n"
        "## Recommended Next Step\n"
        "Verify the account status before preparing a recommendation. [F1][P1]",
        SyntheticKycState(False, False, False),
    )

    assert assessment.passed is True


def test_quality_allows_existing_account_policy_requirement() -> None:
    assessment = evaluate_response_quality(
        DemoMode.CUSTOMER_SERVICING,
        "Explain whether this ATM fee qualifies for reversal.",
        "## Request Assessment\n"
        "The $35 ATM fee is eligible for policy review. [F1]\n\n"
        "## Safety Checks\n"
        "The policy requires that the account is open and in good standing. [P1]\n\n"
        "## Recommended Next Step\n"
        "Verify the account status before preparing a recommendation. [F1][P1]",
        SyntheticKycState(False, False, False),
    )

    assert assessment.passed is True


def test_quality_rejects_direct_open_claim_during_kyc_workflow() -> None:
    assessment = evaluate_response_quality(
        DemoMode.CUSTOMER_SERVICING,
        "Help me open a checking account.",
        "## Request Assessment\n"
        "Your account is open. [C1]\n\n"
        "## Safety Checks\n"
        "The application was reviewed. [C1]\n\n"
        "## Recommended Next Step\n"
        "Review the account details. [C1]",
        SyntheticKycState(True, True, True),
    )

    assert assessment.passed is False
    assert any(issue.code == "unsafe_completion_claim" for issue in assessment.issues)


def test_salary_dlp_keeps_input_strict_and_output_contextual() -> None:
    assert evaluate_salary_dlp("Use my salary record.").blocked is True
    assert evaluate_salary_output_dlp("I cannot process salary or payroll data.").blocked is False
    assert evaluate_salary_output_dlp("A qualifying payroll direct deposit may waive the fee.").blocked is False
    assert evaluate_salary_output_dlp("Your salary is $100,000 per year.").blocked is True
