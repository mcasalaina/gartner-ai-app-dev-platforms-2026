from __future__ import annotations

import re
from dataclasses import dataclass

from bank_servicing_agent.dlp import evaluate_salary_output_dlp
from bank_servicing_agent.kyc_state import SyntheticKycState, find_confirmation_safety_issues
from bank_servicing_agent.modes import DemoMode


@dataclass(frozen=True, slots=True)
class QualityIssue:
    code: str
    detail: str
    repairable: bool = True


@dataclass(frozen=True, slots=True)
class QualityAssessment:
    passed: bool
    issues: tuple[QualityIssue, ...]
    word_count: int


_REQUIRED_HEADINGS = {
    DemoMode.SERVICE_DISCOVERY: (
        "## Service Summary",
        "## Evidence",
        "## Recommended Next Step",
    ),
    DemoMode.CUSTOMER_SERVICING: (
        "## Request Assessment",
        "## Safety Checks",
        "## Recommended Next Step",
    ),
}
_WORD_LIMITS = {
    DemoMode.SERVICE_DISCOVERY: 220,
    DemoMode.CUSTOMER_SERVICING: 260,
}
_CITATION_PATTERN = re.compile(r"\[[A-Z][A-Z0-9:-]*\]")
_INTERNAL_CONTEXT_PATTERN = re.compile(r"\b(?:demo|synthetic)\b", re.IGNORECASE)



def evaluate_response_quality(
    mode: DemoMode,
    user_text: str,
    response_text: str,
    kyc_state: SyntheticKycState,
) -> QualityAssessment:
    issues: list[QualityIssue] = []
    word_count = len(re.findall(r"\S+", response_text))
    if word_count > _WORD_LIMITS[mode]:
        issues.append(
            QualityIssue(
                code="too_long",
                detail=f"Response exceeded {_WORD_LIMITS[mode]} words.",
            )
        )
    for heading in _REQUIRED_HEADINGS[mode]:
        if heading not in response_text:
            issues.append(
                QualityIssue(
                    code="missing_section",
                    detail=f"Missing required section heading: {heading}",
                )
            )
    if not _CITATION_PATTERN.search(response_text):
        issues.append(
            QualityIssue(
                code="missing_citation",
                detail="At least one citation marker is required.",
            )
        )
    if _INTERNAL_CONTEXT_PATTERN.search(response_text):
        issues.append(
            QualityIssue(
                code="internal_context_disclosure",
                detail=(
                    "The response exposed an internal environment or evaluation label "
                    "instead of speaking naturally as the bank-servicing agent."
                ),
            )
        )
    if not _is_relevant(user_text, response_text, mode):
        issues.append(
            QualityIssue(
                code="low_relevance",
                detail="The response does not clearly address the user request.",
            )
        )
    dlp_result = evaluate_salary_output_dlp(response_text)
    if dlp_result.blocked:
        issues.append(
            QualityIssue(
                code="salary_dlp_output",
                detail="The response included blocked salary or payroll content.",
                repairable=False,
            )
        )
    for code in find_confirmation_safety_issues(response_text, kyc_state):
        issues.append(
            QualityIssue(
                code=code,
                detail=code.replace("_", " "),
                repairable=code != "unsafe_completion_claim",
            )
        )
    return QualityAssessment(
        passed=not issues,
        issues=tuple(issues),
        word_count=word_count,
    )



def _is_relevant(user_text: str, response_text: str, mode: DemoMode) -> bool:
    request_tokens = {token for token in re.findall(r"[a-z0-9]+", user_text.lower()) if len(token) > 3}
    response_tokens = set(re.findall(r"[a-z0-9]+", response_text.lower()))
    if request_tokens & response_tokens:
        return True
    mode_terms = {
        DemoMode.SERVICE_DISCOVERY: {"service", "product", "branch", "account", "loan", "card"},
        DemoMode.CUSTOMER_SERVICING: {"request", "safety", "next", "account", "kyc", "application"},
    }
    return bool(mode_terms[mode] & response_tokens)
