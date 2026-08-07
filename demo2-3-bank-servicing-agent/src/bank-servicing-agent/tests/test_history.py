from __future__ import annotations

from bank_servicing_agent.history import split_latest_user_turn


def test_split_latest_user_turn_separates_current_input_from_client_history() -> None:
    current, history = split_latest_user_turn(
        [
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "Compare checking and savings."}],
            },
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "Checking is for daily spending."}],
            },
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "Which one fits daily spending?"}],
            },
        ]
    )

    assert current == "Which one fits daily spending?"
    assert tuple((turn.role, turn.text) for turn in history) == (
        ("user", "Compare checking and savings."),
        ("assistant", "Checking is for daily spending."),
    )
