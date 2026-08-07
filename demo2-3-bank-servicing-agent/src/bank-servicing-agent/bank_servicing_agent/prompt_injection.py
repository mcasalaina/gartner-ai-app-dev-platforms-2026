from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class PromptInjectionMarker:
    code: str
    matched_text: str
    severity: str


_MARKERS: tuple[tuple[str, str, str], ...] = (
    ("override_instructions", r"ignore (all|the|previous|prior) (instructions|system prompt)", "high"),
    ("reveal_hidden_prompt", r"(reveal|print|dump).*(system prompt|hidden instructions|developer message)", "high"),
    ("mode_tampering", r"x-client-demo-mode|switch .* mode|change .* mode", "high"),
    ("credential_exfiltration", r"(bearer token|authorization header|api key|call-id)", "high"),
    ("tool_schema_exfiltration", r"(tool schema|tool json|list your hidden tools)", "medium"),
)



def detect_prompt_injection_markers(text: str) -> tuple[PromptInjectionMarker, ...]:
    lowered = text.lower()
    markers: list[PromptInjectionMarker] = []
    for code, pattern, severity in _MARKERS:
        match = re.search(pattern, lowered, re.IGNORECASE | re.DOTALL)
        if match:
            markers.append(
                PromptInjectionMarker(
                    code=code,
                    matched_text=match.group(0),
                    severity=severity,
                )
            )
    return tuple(markers)



def has_high_severity_marker(markers: tuple[PromptInjectionMarker, ...]) -> bool:
    return any(marker.severity == "high" for marker in markers)
