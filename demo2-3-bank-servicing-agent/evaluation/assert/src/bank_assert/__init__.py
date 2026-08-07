"""ASSERT beta integration for the Bank Servicing Agent."""

__all__ = ["chat"]


async def chat(message: str, history: list[dict[str, str]]) -> str:
    from bank_assert.target import chat as target_chat

    return await target_chat(message, history)
