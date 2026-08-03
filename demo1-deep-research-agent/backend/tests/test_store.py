from pathlib import Path

from app.models import ResearchRun, RunStatus, WorkflowEvent
from app.store import RunStore


def test_store_round_trip(tmp_path: Path):
    store = RunStore(tmp_path / "runs.db")
    run = ResearchRun(id="run-1", prompt="x" * 40, status=RunStatus.PLANNING)
    store.save_run(run)
    event = store.append_event(
        WorkflowEvent(run_id=run.id, type="run.created", message="Created")
    )

    restored = store.get_run(run.id)
    assert restored is not None
    assert restored.status == RunStatus.PLANNING
    assert event.sequence > 0
    assert store.list_events(run.id)[0].message == "Created"
