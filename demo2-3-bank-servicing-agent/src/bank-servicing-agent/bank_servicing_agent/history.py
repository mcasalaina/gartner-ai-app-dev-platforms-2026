from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from bank_servicing_agent.models import ConversationTurn


def extract_conversation_turns(
    history_items: Sequence[object] | None,
) -> tuple[ConversationTurn, ...]:
    turns: list[ConversationTurn] = []
    for item in history_items or ():
        if _read(item, "type") != "message":
            continue
        role = str(_read(item, "role") or "assistant")
        text_parts: list[str] = []
        for part in _read(item, "content") or []:
            part_type = _read(part, "type")
            if part_type not in {"output_text", "input_text", "text"}:
                continue
            text_value = _read(part, "text")
            if isinstance(text_value, str):
                text_parts.append(text_value)
                continue
            nested_value = _read(text_value, "value") if text_value is not None else None
            if isinstance(nested_value, str):
                text_parts.append(nested_value)
                continue
            direct_value = _read(part, "value")
            if isinstance(direct_value, str):
                text_parts.append(direct_value)
        text = "\n".join(piece.strip() for piece in text_parts if piece.strip())
        if text:
            turns.append(ConversationTurn(role=role, text=text))
    return tuple(turns)


def split_latest_user_turn(
    input_items: Sequence[object] | None,
) -> tuple[str, tuple[ConversationTurn, ...]]:
    turns = extract_conversation_turns(input_items)
    for index in range(len(turns) - 1, -1, -1):
        if turns[index].role.casefold() == "user":
            return turns[index].text, turns[:index]
    return "", turns


def render_history(turns: tuple[ConversationTurn, ...], max_turns: int = 8) -> str:
    selected = turns[-max_turns:]
    if not selected:
        return "(no prior conversation history)"
    return "\n\n".join(
        f"{turn.role.upper()}: {turn.text.strip()}" for turn in selected if turn.text.strip()
    )


def _read(value: object, key: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(key)
    return getattr(value, key, None)
