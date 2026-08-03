from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


def utc_now() -> datetime:
    return datetime.now(UTC)


class RunStatus(StrEnum):
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    RESEARCHING = "researching"
    SYNTHESIZING = "synthesizing"
    GENERATING_ARTIFACTS = "generating_artifacts"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class PlanSection(BaseModel):
    id: str
    title: str
    objective: str
    search_questions: list[str] = Field(default_factory=list)
    evaluation_criteria: list[str] = Field(default_factory=list)


class ResearchPlan(BaseModel):
    refined_request: str
    objectives: list[str]
    assumptions: list[str] = Field(default_factory=list)
    methods: list[str]
    evaluation_criteria: list[str]
    sections: list[PlanSection]
    revision: int = 1


class Citation(BaseModel):
    id: str
    title: str
    url: HttpUrl
    publisher: str | None = None
    published_at: str | None = None
    accessed_at: datetime = Field(default_factory=utc_now)
    claims: list[str] = Field(default_factory=list)


class Artifact(BaseModel):
    name: str
    kind: str
    url: str
    content_type: str
    bytes: int


class WorkflowStage(BaseModel):
    id: str
    label: str
    actor: str
    model: str | None = None
    status: StageStatus = StageStatus.PENDING
    detail: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class InputAttachment(BaseModel):
    name: str
    content_type: str
    bytes: int
    summary: str


class EvaluationSummary(BaseModel):
    groundedness: float
    citation_completeness: float
    plan_coverage: float
    source_quality: float
    passed: bool


class ResearchRun(BaseModel):
    id: str
    prompt: str
    research_depth: str = "executive"
    status: RunStatus
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    plan: ResearchPlan | None = None
    attachments: list[InputAttachment] = Field(default_factory=list)
    stages: list[WorkflowStage] = Field(default_factory=list)
    report_markdown: str | None = None
    highlighted_chapter: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    artifacts: list[Artifact] = Field(default_factory=list)
    evaluation: EvaluationSummary | None = None
    error: str | None = None


class WorkflowEvent(BaseModel):
    sequence: int = 0
    run_id: str
    type: str
    stage_id: str | None = None
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class PlanUpdate(BaseModel):
    plan: ResearchPlan


class AgentRequest(BaseModel):
    action: str
    run_id: str
    prompt: str
    research_depth: str
    attachment_summaries: list[str] = Field(default_factory=list)
    plan: ResearchPlan | None = None


class ResearchResult(BaseModel):
    report_markdown: str
    highlighted_chapter: str
    citations: list[Citation]
    evaluation: EvaluationSummary
    service_scores: dict[str, float] = Field(default_factory=dict)
