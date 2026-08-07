from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class SalaryDlpResult:
    blocked: bool
    matches: tuple[str, ...]


_PATTERNS = (
    r"\bsalary\b",
    r"\bcompensation\b",
    r"\bpayroll\b",
    r"\bpaystub\b",
    r"\bw-?2\b",
    r"\b1099\b",
    r"\bhourly wage\b",
    r"\bbase pay\b",
    r"\bbonus\b",
)
_SENSITIVE_OUTPUT_PATTERNS = (
    (
        "subject_salary_reference",
        r"\b(?:your|customer(?:'s)?|applicant(?:'s)?|employee(?:'s)?|their|his|her)\s+"
        r"(?:salary|compensation|payroll|paystub|w-?2|1099|hourly wage|base pay|bonus)\b",
    ),
    (
        "salary_value_statement",
        r"\b(?:salary|compensation|hourly wage|base pay|bonus)\s+"
        r"(?:is|was|of|amount|total|equals?)\b",
    ),
    (
        "salary_term_with_amount",
        r"\b(?:salary|compensation|payroll|paystub|w-?2|1099|hourly wage|base pay|bonus)\b"
        r".{0,40}(?:\$\s?\d|\b\d+(?:[,.]\d+)*(?:\s?(?:usd|dollars|per\s+(?:hour|year)))?)",
    ),
    (
        "salary_amount_with_term",
        r"(?:\$\s?\d|\b\d+(?:[,.]\d+)*(?:\s?(?:usd|dollars|per\s+(?:hour|year)))?).{0,40}"
        r"\b(?:salary|compensation|payroll|paystub|w-?2|1099|hourly wage|base pay|bonus)\b",
    ),
)


def evaluate_salary_dlp(text: str) -> SalaryDlpResult:
    lowered = text.lower()
    matches = tuple(
        pattern.replace("\\b", "")
        for pattern in _PATTERNS
        if re.search(pattern, lowered, re.IGNORECASE)
    )
    return SalaryDlpResult(blocked=bool(matches), matches=matches)


def evaluate_salary_output_dlp(text: str) -> SalaryDlpResult:
    matches = tuple(
        code
        for code, pattern in _SENSITIVE_OUTPUT_PATTERNS
        if re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    )
    return SalaryDlpResult(blocked=bool(matches), matches=matches)
