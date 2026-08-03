from pathlib import Path

import pytest

from app.models import AgentRequest, RunStatus
from app.store import RunStore
from app.workflow import RunService


class FakeGateway:
    async def invoke(self, request: AgentRequest) -> dict:
        if request.action == "plan":
            return {
                "plan": {
                    "refined_request": request.prompt,
                    "objectives": ["Build an evidence-backed strategy"],
                    "assumptions": [],
                    "methods": ["Parallel Web IQ research"],
                    "evaluation_criteria": ["Every material claim is cited"],
                    "sections": [
                        {
                            "id": "market",
                            "title": "Market opportunity",
                            "objective": "Assess the opportunity",
                            "search_questions": ["What is changing?"],
                            "evaluation_criteria": ["Use authoritative sources"],
                        }
                    ],
                    "revision": 1,
                }
            }
        return {
            "report_markdown": "# Strategy\n\nEvidence-backed recommendation [s1].",
            "highlighted_chapter": "Prioritize compliant commercial banking.",
            "citations": [
                {
                    "id": "s1",
                    "title": "Official source",
                    "url": "https://example.com/source",
                    "claims": ["Evidence-backed recommendation"],
                }
            ],
            "evaluation": {
                "groundedness": 0.95,
                "citation_completeness": 0.95,
                "plan_coverage": 0.9,
                "source_quality": 0.9,
                "passed": True,
            },
            "service_scores": {"Commercial banking": 90},
        }


class FakeArtifacts:
    def __init__(self):
        self.calls = 0

    async def generate(self, run_id, result):
        self.calls += 1
        return []


@pytest.mark.asyncio
async def test_run_requires_approval_then_completes(tmp_path: Path):
    store = RunStore(tmp_path / "runs.db")
    service = RunService(store, FakeGateway(), FakeArtifacts())
    run = service.create_run("Develop a global bank strategy." * 3, "executive", [])

    await service._tasks[run.id]
    planned = store.get_run(run.id)
    assert planned.status == RunStatus.AWAITING_APPROVAL

    service.approve(run.id)
    await service._tasks[run.id]
    completed = store.get_run(run.id)
    assert completed.status == RunStatus.COMPLETE
    assert completed.citations[0].id == "s1"


@pytest.mark.asyncio
async def test_failed_artifacts_can_retry_without_research(tmp_path: Path):
    class FailsOnceArtifacts(FakeArtifacts):
        async def generate(self, run_id, result):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("image generation failed")
            return []

    store = RunStore(tmp_path / "runs.db")
    artifacts = FailsOnceArtifacts()
    service = RunService(store, FakeGateway(), artifacts)
    run = service.create_run("Develop a global bank strategy." * 3, "executive", [])
    await service._tasks[run.id]
    service.approve(run.id)
    await service._tasks[run.id]

    failed = store.get_run(run.id)
    assert failed.status == RunStatus.FAILED
    assert failed.report_markdown

    service.retry_artifacts(run.id)
    await service._tasks[run.id]
    completed = store.get_run(run.id)
    assert completed.status == RunStatus.COMPLETE
    assert artifacts.calls == 2
