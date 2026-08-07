from __future__ import annotations

from dataclasses import dataclass
import re

from bank_servicing_agent.models import ConversationTurn


@dataclass(frozen=True, slots=True)
class SyntheticKycState:
    workflow_requested: bool
    user_confirmed_submission: bool
    user_confirmed_disclosures: bool


_COMPLETION_PATTERNS = (
    r"\baccount (is|was) now open\b",
    r"\bi (have )?opened your account\b",
    r"\bkyc (is )?(complete|completed|approved)\b",
    r"\bapplication (is )?(submitted|approved)\b",
    r"\bidentity (is )?verified\b",
)
_WORKFLOW_COMPLETION_PATTERNS = (
    r"\b(?:your|new|the new) account (?:is|was) open\b",
)
_NEGATION_PATTERN = re.compile(
    r"\b(?:no|not|never|cannot|can't|do not|does not|did not|should not|must not)\b"
)
_CONDITIONAL_PATTERN = re.compile(
    r"\b(?:if|assuming|provided(?: that)?|when|whether)\b"
)


def derive_synthetic_kyc_state(
    history: tuple[ConversationTurn, ...],
    current_user_text: str,
) -> SyntheticKycState:
    user_text = "\n".join(
        [turn.text for turn in history if turn.role == "user"] + [current_user_text]
    ).lower()
    return SyntheticKycState(
        workflow_requested=bool(
            re.search(r"\b(open|apply|application|kyc|verify)\b", user_text)
        ),
        user_confirmed_submission=bool(
            re.search(
                r"\b(i confirm|yes submit|please submit|proceed with (the )?application)\b",
                user_text,
            )
        ),
        user_confirmed_disclosures=bool(
            re.search(r"\b(i agree|i acknowledge|i confirm disclosures)\b", user_text)
        ),
    )


def find_confirmation_safety_issues(
    text: str,
    state: SyntheticKycState,
) -> tuple[str, ...]:
    lowered = text.lower()
    completion_patterns = _COMPLETION_PATTERNS + (
        _WORKFLOW_COMPLETION_PATTERNS if state.workflow_requested else ()
    )
    issues = [
        "unsafe_completion_claim"
        for pattern in completion_patterns
        for match in re.finditer(pattern, lowered)
        if not _is_non_assertive_claim(lowered, match.start())
    ]
    if state.workflow_requested and "confirm" not in lowered and "next step" not in lowered:
        issues.append("missing_confirmation_guidance")
    return tuple(dict.fromkeys(issues))


def _is_non_assertive_claim(text: str, claim_start: int) -> bool:
    prefix = text[max(0, claim_start - 80) : claim_start]
    sentence_boundary = max(
        prefix.rfind("."),
        prefix.rfind("!"),
        prefix.rfind("?"),
        prefix.rfind("\n"),
    )
    sentence_prefix = prefix[sentence_boundary + 1 :]
    return bool(
        _NEGATION_PATTERN.search(sentence_prefix)
        or _CONDITIONAL_PATTERN.search(sentence_prefix)
    )
