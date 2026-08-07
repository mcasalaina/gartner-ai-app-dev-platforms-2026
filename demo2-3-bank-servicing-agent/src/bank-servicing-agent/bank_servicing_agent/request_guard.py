from __future__ import annotations

from dataclasses import dataclass
import re

from bank_servicing_agent.modes import DemoMode


@dataclass(frozen=True, slots=True)
class GuardDecision:
    allowed: bool
    code: str
    message: str


_GENERAL_BANK_TERMS = {
    "bank",
    "banking",
    "account",
    "checking",
    "savings",
    "loan",
    "card",
    "branch",
    "mortgage",
    "deposit",
    "investment",
    "wire",
    "fee",
    "overdraft",
    "kyc",
    "service",
}
_SERVICE_DISCOVERY_TERMS = {
    "service",
    "product",
    "compare",
    "branch",
    "hours",
    "rates",
    "features",
    "offerings",
}
_CUSTOMER_SERVICING_TERMS = {
    "open",
    "application",
    "kyc",
    "verify",
    "servicing",
    "dispute",
    "fee",
    "address",
    "statement",
    "card",
    "wire",
}
_BANK_DOMAIN_TERMS = (
    _GENERAL_BANK_TERMS | _SERVICE_DISCOVERY_TERMS | _CUSTOMER_SERVICING_TERMS
)
_CROSS_USER_PATTERN = re.compile(
    r"\b(another|different|other)\s+(customer|user|account holder)\b|"
    r"\b(someone else|not my account)\b",
    re.IGNORECASE,
)



def evaluate_bank_domain_request(mode: DemoMode, text: str) -> GuardDecision:
    tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
    tokens.update(
        token[:-1] for token in tuple(tokens) if token.endswith("s") and len(token) > 3
    )
    if not tokens & _BANK_DOMAIN_TERMS:
        return GuardDecision(
            allowed=False,
            code="out_of_domain",
            message="I can only help with banking services and customer servicing.",
        )
    if mode is DemoMode.SERVICE_DISCOVERY and tokens & {"dispute", "application", "kyc", "statement"}:
        return GuardDecision(
            allowed=False,
            code="mode_mismatch",
            message=(
                "This surface is in service discovery mode. Use the customer-servicing "
                "experience for KYC, account-opening, or servicing actions."
            ),
        )
    if mode is DemoMode.CUSTOMER_SERVICING and tokens & {"compare", "rates", "offerings", "features"}:
        return GuardDecision(
            allowed=False,
            code="mode_mismatch",
            message=(
                "This surface is in customer-servicing mode. Use the service-discovery "
                "experience for product comparison or general service exploration."
            ),
        )
    if mode is DemoMode.SERVICE_DISCOVERY and not tokens & (_SERVICE_DISCOVERY_TERMS | _GENERAL_BANK_TERMS):
        return GuardDecision(
            allowed=False,
            code="out_of_scope",
            message="Please ask about banking services, products, branches, or eligibility guidance.",
        )
    if mode is DemoMode.CUSTOMER_SERVICING and not tokens & (_CUSTOMER_SERVICING_TERMS | _GENERAL_BANK_TERMS):
        return GuardDecision(
            allowed=False,
            code="out_of_scope",
            message="Please ask about a servicing, KYC, or account-opening workflow.",
        )
    return GuardDecision(allowed=True, code="allowed", message="")


def evaluate_cross_user_request(text: str) -> GuardDecision:
    if _CROSS_USER_PATTERN.search(text):
        return GuardDecision(
            allowed=False,
            code="cross_user",
            message=(
                "I can't access or disclose another customer's information. "
                "Continue only with the current customer's case."
            ),
        )
    return GuardDecision(allowed=True, code="allowed", message="")
