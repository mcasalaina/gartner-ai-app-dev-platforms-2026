from __future__ import annotations

import re


_SPANISH_MARKERS = {
    "abrir",
    "ahorros",
    "banco",
    "beneficios",
    "comparar",
    "cuenta",
    "identidad",
    "producto",
    "servicio",
    "verificar",
}


def uses_spanish(text: str) -> bool:
    tokens = set(re.findall(r"\w+", text.casefold(), re.UNICODE))
    return bool(tokens & _SPANISH_MARKERS)


def avatar_section_headings(user_text: str) -> tuple[str, str, str]:
    if uses_spanish(user_text):
        return (
            "## Resumen del servicio",
            "## Evidencia",
            "## Próximo paso recomendado",
        )
    return (
        "## Service Summary",
        "## Evidence",
        "## Recommended Next Step",
    )
