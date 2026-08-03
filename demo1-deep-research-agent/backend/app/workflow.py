import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from .artifacts import ArtifactGenerator
from .gateway import AgentGateway
from .models import (
    AgentRequest,
    InputAttachment,
    PlanUpdate,
    ResearchPlan,
    ResearchResult,
    ResearchRun,
    RunStatus,
    StageStatus,
    WorkflowEvent,
    WorkflowStage,
)
from .store import RunStore


def now() -> datetime:
    return datetime.now(UTC)


class RunService:
    def __init__(
        self,
        store: RunStore,
        gateway: AgentGateway,
        artifacts: ArtifactGenerator,
    ):
        self.store = store
        self.gateway = gateway
        self.artifacts = artifacts
        self._tasks: dict[str, asyncio.Task] = {}

    def create_run(
        self,
        prompt: str,
        research_depth: str,
        attachments: list[InputAttachment],
    ) -> ResearchRun:
        run_id = uuid4().hex
        stages = [
            WorkflowStage(id="plan", label="Research plan", actor="Strategy Planner", model="gpt-5.4-mini"),
            WorkflowStage(id="approval", label="Human approval", actor="Demo operator"),
            WorkflowStage(id="research", label="Parallel research", actor="Research Council", model="gpt-5.4-mini + Web IQ"),
            WorkflowStage(id="review", label="Evidence review", actor="Quality Reviewer", model="gpt-5.4-mini"),
            WorkflowStage(id="synthesis", label="Report synthesis", actor="Executive Editor", model="gpt-5.4-mini"),
            WorkflowStage(id="artifacts", label="Visuals, speech, PDF", actor="Artifact Studio", model="FLUX-1.1-pro + Speech"),
        ]
        run = ResearchRun(
            id=run_id,
            prompt=prompt,
            research_depth=research_depth,
            status=RunStatus.PLANNING,
            attachments=attachments,
            stages=stages,
        )
        self.store.save_run(run)
        self._tasks[run_id] = asyncio.create_task(self._plan(run_id))
        return run

    def update_plan(self, run_id: str, update: PlanUpdate) -> ResearchRun:
        run = self._require_run(run_id)
        if run.status != RunStatus.AWAITING_APPROVAL:
            raise ValueError("The plan can only be edited before approval.")
        update.plan.revision = (run.plan.revision if run.plan else 0) + 1
        run.plan = update.plan
        run.updated_at = now()
        self.store.save_run(run)
        self._emit(run_id, "plan.updated", "approval", "Research plan revision saved.")
        return run

    def approve(self, run_id: str) -> ResearchRun:
        run = self._require_run(run_id)
        if run.status != RunStatus.AWAITING_APPROVAL or not run.plan:
            raise ValueError("A completed research plan is required before approval.")
        self._set_stage(run, "approval", StageStatus.COMPLETE, "Plan approved.")
        run.status = RunStatus.RESEARCHING
        run.updated_at = now()
        self.store.save_run(run)
        self._emit(run_id, "plan.approved", "approval", "Plan approved; live research started.")
        self._tasks[run_id] = asyncio.create_task(self._research(run_id))
        return run

    def cancel(self, run_id: str) -> ResearchRun:
        run = self._require_run(run_id)
        task = self._tasks.get(run_id)
        if task and not task.done():
            task.cancel()
        run.status = RunStatus.CANCELLED
        run.updated_at = now()
        self.store.save_run(run)
        self._emit(run_id, "run.cancelled", None, "Run cancelled by the operator.")
        return run

    def retry_artifacts(self, run_id: str) -> ResearchRun:
        run = self._require_run(run_id)
        artifact_stage = next(stage for stage in run.stages if stage.id == "artifacts")
        active_task = self._tasks.get(run_id)
        if (
            run.status not in {RunStatus.FAILED, RunStatus.GENERATING_ARTIFACTS}
            or artifact_stage.status not in {StageStatus.FAILED, StageStatus.RUNNING}
            or (active_task is not None and not active_task.done())
            or not run.report_markdown
            or not run.highlighted_chapter
            or not run.evaluation
        ):
            raise ValueError(
                "Only an inactive failed or interrupted artifact stage with a "
                "completed report can be retried."
            )
        run.status = RunStatus.GENERATING_ARTIFACTS
        run.error = None
        self._set_stage(run, "artifacts", StageStatus.RUNNING, "Retrying multimodal outputs.")
        run.updated_at = now()
        self.store.save_run(run)
        self._emit(run_id, "stage.retried", "artifacts", "Artifact generation retried.")
        self._tasks[run_id] = asyncio.create_task(self._retry_artifacts(run_id))
        return run

    async def _plan(self, run_id: str) -> None:
        run = self._require_run(run_id)
        self._set_stage(run, "plan", StageStatus.RUNNING, "Refining and decomposing the request.")
        self.store.save_run(run)
        self._emit(run_id, "stage.started", "plan", "Strategy Planner is building the research plan.")
        try:
            payload = await self.gateway.invoke(
                AgentRequest(
                    action="plan",
                    run_id=run.id,
                    prompt=run.prompt,
                    research_depth=run.research_depth,
                    attachment_summaries=[item.summary for item in run.attachments],
                )
            )
            run.plan = ResearchPlan.model_validate(payload["plan"])
            run.status = RunStatus.AWAITING_APPROVAL
            self._set_stage(run, "plan", StageStatus.COMPLETE, "Structured plan ready.")
            self._set_stage(run, "approval", StageStatus.RUNNING, "Waiting for operator review.")
            run.updated_at = now()
            self.store.save_run(run)
            self._emit(run_id, "plan.ready", "plan", "Research plan is ready for review.")
        except Exception as exc:
            self._fail(run, "plan", exc)

    async def _research(self, run_id: str) -> None:
        run = self._require_run(run_id)
        self._set_stage(run, "research", StageStatus.RUNNING, "Specialists are researching in parallel.")
        self.store.save_run(run)
        self._emit(
            run_id,
            "stage.started",
            "research",
            f"Launching {len(run.plan.sections)} cited research assignments.",
        )
        try:
            payload = await self.gateway.invoke(
                AgentRequest(
                    action="research",
                    run_id=run.id,
                    prompt=run.prompt,
                    research_depth=run.research_depth,
                    attachment_summaries=[item.summary for item in run.attachments],
                    plan=run.plan,
                )
            )
            result = ResearchResult.model_validate(payload)
            run.report_markdown = result.report_markdown
            run.highlighted_chapter = result.highlighted_chapter
            run.citations = result.citations
            run.evaluation = result.evaluation
            self._set_stage(run, "research", StageStatus.COMPLETE, "Parallel research complete.")
            self._set_stage(run, "review", StageStatus.COMPLETE, "Evidence and citations reconciled.")
            self._set_stage(run, "synthesis", StageStatus.COMPLETE, "Executive report synthesized.")
            run.status = RunStatus.GENERATING_ARTIFACTS
            self._set_stage(run, "artifacts", StageStatus.RUNNING, "Generating live multimodal outputs.")
            run.updated_at = now()
            self.store.save_run(run)
            self._emit(run_id, "report.ready", "synthesis", "Cited report and service chapter are ready.")

            await self._complete_artifacts(run, result)
        except Exception as exc:
            stage = "artifacts" if run.status == RunStatus.GENERATING_ARTIFACTS else "research"
            self._fail(run, stage, exc)

    async def _retry_artifacts(self, run_id: str) -> None:
        run = self._require_run(run_id)
        result = ResearchResult(
            report_markdown=run.report_markdown,
            highlighted_chapter=run.highlighted_chapter,
            citations=run.citations,
            evaluation=run.evaluation,
        )
        try:
            await self._complete_artifacts(run, result)
        except Exception as exc:
            self._fail(run, "artifacts", exc)

    async def _complete_artifacts(
        self, run: ResearchRun, result: ResearchResult
    ) -> None:
        run.artifacts = await self.artifacts.generate(run.id, result)
        self._set_stage(
            run,
            "artifacts",
            StageStatus.COMPLETE,
            "Image, narration, chart, and PDF ready.",
        )
        run.status = RunStatus.COMPLETE
        run.updated_at = now()
        self.store.save_run(run)
        self._emit(run.id, "run.complete", "artifacts", "All live research artifacts are ready.")

    def _fail(self, run: ResearchRun, stage_id: str, exc: Exception) -> None:
        run.status = RunStatus.FAILED
        run.error = str(exc)
        run.updated_at = now()
        self._set_stage(run, stage_id, StageStatus.FAILED, str(exc))
        self.store.save_run(run)
        self._emit(run.id, "run.failed", stage_id, str(exc))

    def _set_stage(
        self,
        run: ResearchRun,
        stage_id: str,
        status: StageStatus,
        detail: str,
    ) -> None:
        stage = next(stage for stage in run.stages if stage.id == stage_id)
        stage.status = status
        stage.detail = detail
        if status == StageStatus.RUNNING:
            stage.started_at = now()
        if status in {StageStatus.COMPLETE, StageStatus.FAILED}:
            stage.completed_at = now()

    def _emit(
        self, run_id: str, event_type: str, stage_id: str | None, message: str
    ) -> None:
        self.store.append_event(
            WorkflowEvent(
                run_id=run_id,
                type=event_type,
                stage_id=stage_id,
                message=message,
            )
        )

    def _require_run(self, run_id: str) -> ResearchRun:
        run = self.store.get_run(run_id)
        if not run:
            raise KeyError(run_id)
        return run
