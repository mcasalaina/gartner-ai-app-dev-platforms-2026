import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from azure.monitor.opentelemetry import configure_azure_monitor
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from .artifacts import ArtifactGenerator
from .config import Settings
from .gateway import AgentGateway
from .models import PlanUpdate, ResearchRun, RunStatus
from .normalizer import normalize_upload
from .store import RunStore
from .workflow import RunService

settings = Settings()
if settings.applicationinsights_connection_string:
    configure_azure_monitor(logger_name="gartner.deep_research")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
    store = RunStore(settings.database_path)
    app.state.run_service = RunService(
        store,
        AgentGateway(
            settings.foundry_agent_endpoint,
            settings.foundry_agent_api_version,
        ),
        ArtifactGenerator(settings),
    )
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.allowed_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def service(request: Request) -> RunService:
    return request.app.state.run_service


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.post("/api/runs", response_model=ResearchRun, status_code=202)
async def create_run(
    request: Request,
    prompt: str = Form(..., min_length=40),
    research_depth: str = Form("executive"),
    files: list[UploadFile] = File(default=[]),
) -> ResearchRun:
    run_dir = settings.artifacts_dir / "uploads"
    try:
        attachments = [
            await normalize_upload(upload, run_dir) for upload in files
        ]
        return service(request).create_run(prompt, research_depth, attachments)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/runs/{run_id}", response_model=ResearchRun)
async def get_run(run_id: str, request: Request) -> ResearchRun:
    run = service(request).store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    return run


@app.post("/api/runs/{run_id}/plan", response_model=ResearchRun)
async def update_plan(
    run_id: str, update: PlanUpdate, request: Request
) -> ResearchRun:
    try:
        return service(request).update_plan(run_id, update)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/runs/{run_id}/approve", response_model=ResearchRun)
async def approve_run(run_id: str, request: Request) -> ResearchRun:
    try:
        return service(request).approve(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/runs/{run_id}/cancel", response_model=ResearchRun)
async def cancel_run(run_id: str, request: Request) -> ResearchRun:
    try:
        return service(request).cancel(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found.") from exc


@app.post("/api/runs/{run_id}/retry-artifacts", response_model=ResearchRun)
async def retry_artifacts(run_id: str, request: Request) -> ResearchRun:
    try:
        return service(request).retry_artifacts(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/runs/{run_id}/events")
async def stream_events(run_id: str, request: Request) -> StreamingResponse:
    store = service(request).store
    if not store.get_run(run_id):
        raise HTTPException(status_code=404, detail="Run not found.")

    async def event_stream():
        sequence = int(request.headers.get("last-event-id", "0"))
        while True:
            events = store.list_events(run_id, sequence)
            for event in events:
                sequence = event.sequence
                yield (
                    f"id: {event.sequence}\n"
                    f"event: {event.type}\n"
                    f"data: {event.model_dump_json()}\n\n"
                )
            run = store.get_run(run_id)
            if run and run.status in {
                RunStatus.COMPLETE,
                RunStatus.FAILED,
                RunStatus.CANCELLED,
            }:
                yield f"event: stream.closed\ndata: {json.dumps({'run_id': run_id})}\n\n"
                break
            yield ": heartbeat\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/runs/{run_id}/artifacts/{name}")
async def get_artifact(run_id: str, name: str, request: Request) -> FileResponse:
    run = service(request).store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    safe_name = Path(name).name
    artifact = next((item for item in run.artifacts if item.name == safe_name), None)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    path = settings.artifacts_dir / run_id / safe_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Artifact file not found.")
    return FileResponse(path, media_type=artifact.content_type, filename=safe_name)
