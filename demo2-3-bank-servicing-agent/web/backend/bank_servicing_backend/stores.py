from __future__ import annotations

import uuid
from dataclasses import dataclass
from statistics import median

from .foundry import ChatMessage, FoundryResponse
from .errors import NotFoundError


@dataclass(slots=True)
class QualityMetricsSnapshot:
    comprehensiveness: float | None = None
    accuracy: float | None = None
    latency_p50_ms: float | None = None
    estimated_cost_usd: float | None = None
    _latencies_ms: list[float] | None = None

    def record_latency(self, latency_ms: float) -> None:
        values = self._latencies_ms or []
        values.append(latency_ms)
        self._latencies_ms = values[-200:]
        self.latency_p50_ms = round(median(self._latencies_ms), 2)


@dataclass(slots=True)
class ReviewDraft:
    id: str
    title: str
    status: str
    version: int
    summary: str


class InMemoryConversationStore:
    def __init__(self) -> None:
        self._history: dict[str, list[ChatMessage]] = {}

    def build_request(self, conversation_id: str | None, content: str) -> tuple[str, list[ChatMessage]]:
        resolved_id = conversation_id or uuid.uuid4().hex
        history = list(self._history.get(resolved_id, []))
        history.append(ChatMessage(role="user", content=content))
        return resolved_id, history

    def record_response(self, conversation_id: str, user_content: str, response: FoundryResponse) -> None:
        history = self._history.setdefault(conversation_id, [])
        history.extend(
            [
                ChatMessage(role="user", content=user_content),
                ChatMessage(role="assistant", content=response.text),
            ]
        )


class InMemoryReviewStore:
    def __init__(self, drafts: list[ReviewDraft] | None = None) -> None:
        self._drafts = {
            draft.id: draft
            for draft in (
                drafts
                or [
                    ReviewDraft(
                        id="draft-synthetic-001",
                        title="Banking products landing page",
                        status="pending_review",
                        version=3,
                        summary="Synthetic draft awaiting reviewer approval before publication.",
                    )
                ]
            )
        }

    def list(self) -> list[ReviewDraft]:
        return [self._drafts[key] for key in sorted(self._drafts)]

    def decide(self, draft_id: str, decision: str) -> ReviewDraft:
        draft = self._drafts.get(draft_id)
        if draft is None:
            raise NotFoundError("The requested draft review item was not found")
        status = "approved" if decision == "approve" else "rejected"
        draft.status = status
        draft.version += 1
        return draft
