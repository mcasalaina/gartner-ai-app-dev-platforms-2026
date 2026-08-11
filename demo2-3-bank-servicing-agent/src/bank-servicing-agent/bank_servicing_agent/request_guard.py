from __future__ import annotations

from dataclasses import dataclass
import re
from collections.abc import Sequence

from bank_servicing_agent.modes import DemoMode
from bank_servicing_agent.models import ConversationTurn


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
    "banco",
    "banca",
    "cuenta",
    "cheques",
    "ahorros",
    "préstamo",
    "tarjeta",
    "sucursal",
    "hipoteca",
    "depósito",
    "inversión",
    "transferencia",
    "comisión",
    "sobregiro",
    "servicio",
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
    "servicio",
    "producto",
    "comparar",
    "sucursal",
    "horario",
    "tasas",
    "características",
    "opciones",
    "beneficios",
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
    "abrir",
    "solicitud",
    "identidad",
    "verificar",
    "disputa",
    "comisión",
    "dirección",
    "estado",
    "tarjeta",
    "transferencia",
}
_BANK_DOMAIN_TERMS = (
    _GENERAL_BANK_TERMS | _SERVICE_DISCOVERY_TERMS | _CUSTOMER_SERVICING_TERMS
)
_CROSS_USER_PATTERN = re.compile(
    r"\b(another|different|other)\s+(customer|user|account holder)\b|"
    r"\b(someone else|not my account)\b|"
    r"\b(otro|otra)\s+(cliente|usuario|cuenta)\b|"
    r"\bcuenta\s+de\s+otra\s+persona\b",
    re.IGNORECASE,
)
_CONVERSATIONAL_FOLLOW_UP_PATTERN = re.compile(
    r"\s*(?:(?:okay|ok)\s*,?\s*(?:but\s+)?)?"
    r"(?:can you (?:still )?hear me|are you (?:still )?there|"
    r"what are you doing(?: then)?|what(?:'s| is) happening|"
    r"are you (?:still )?working|keep going|go on|continue|wait|hold on|"
    r"stop|cancel|repeat|say that again|why|how so|okay|ok|yes|no|"
    r"me oyes|sigues ahí|qué estás haciendo|qué pasa|continúa|espera|"
    r"detente|cancela|repite|por qué|sí|no)\s*[?.!]*\s*",
    re.IGNORECASE,
)



def evaluate_bank_domain_request(
    mode: DemoMode,
    text: str,
    history: Sequence[ConversationTurn] = (),
) -> GuardDecision:
    tokens = set(re.findall(r"\w+", text.casefold(), re.UNICODE))
    tokens.update(
        token[:-1] for token in tuple(tokens) if token.endswith("s") and len(token) > 3
    )
    if not tokens & _BANK_DOMAIN_TERMS:
        if _CONVERSATIONAL_FOLLOW_UP_PATTERN.fullmatch(text) and _has_bank_context(history):
            return GuardDecision(allowed=True, code="contextual_follow_up", message="")
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
    if mode is DemoMode.AVATAR_MARKETING and not tokens & _BANK_DOMAIN_TERMS:
        return GuardDecision(
            allowed=False,
            code="out_of_scope",
            message="Please ask about banking services or customer guidance.",
        )
    return GuardDecision(allowed=True, code="allowed", message="")


def _has_bank_context(history: Sequence[ConversationTurn]) -> bool:
    for turn in reversed(history[-8:]):
        if turn.role.casefold() != "user":
            continue
        tokens = set(re.findall(r"\w+", turn.text.casefold(), re.UNICODE))
        tokens.update(
            token[:-1] for token in tuple(tokens) if token.endswith("s") and len(token) > 3
        )
        if tokens & _BANK_DOMAIN_TERMS:
            return True
    return False


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
