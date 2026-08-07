from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bank_assert.app_insights import query_and_import
from bank_assert.config_validation import validate_repository
from bank_assert.gates import evaluate_gates, write_gate_result
from bank_assert.multisource import run_multisource_case
from bank_assert.preflight import run_preflight

MAX_JUDGE_RETRIES = 6


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _evaluation_root() -> Path:
    return _repository_root() / "evaluation" / "assert"


def _score_rows(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _judgment_key(row: dict[str, object]) -> tuple[str, str]:
    return str(row.get("type", "")), str(row.get("test_case_id", ""))


def _unjudged_case_count(inference_path: Path, scores_path: Path) -> int:
    expected = {
        _judgment_key(row)
        for row in _score_rows(inference_path)
        if str(row.get("test_case_id", ""))
    }
    scores = _score_rows(scores_path) if scores_path.is_file() else []
    successful = {
        _judgment_key(row)
        for row in scores
        if row.get("judge_status") == "ok" and str(row.get("test_case_id", ""))
    }
    return len(expected - successful)


def _retain_successful_scores(path: Path) -> None:
    successful_by_key = {
        _judgment_key(row): row
        for row in _score_rows(path)
        if row.get("judge_status") == "ok" and str(row.get("test_case_id", ""))
    }
    path.write_text(
        "".join(
            json.dumps(row, separators=(",", ":")) + "\n"
            for row in successful_by_key.values()
        ),
        encoding="utf-8",
    )


def _run_judge_stage(
    *,
    assert_command: str,
    config: Path,
    suite: str,
    run_id: str,
    artifact_root: Path,
    inference_set: Path,
    save_dir: Path,
    force: bool,
    tolerate_partial_failure: bool,
) -> None:
    command = [
        assert_command,
        "run",
        "--config",
        str(config),
        "--override",
        f"suite={suite}",
        "--override",
        f"run={run_id}",
        "--override",
        f"artifacts_root={artifact_root / '.judge-retries'}",
        "--override",
        "inference.enabled=false",
        "--override",
        f"judge.inference_set_path={inference_set}",
        "--override",
        f"judge.save_dir={save_dir}",
    ]
    if force:
        command.extend(["--force-stage", "judge"])
    process = subprocess.run(command, check=False, env=os.environ.copy())
    if process.returncode == 0:
        return
    scores_path = save_dir / "scores.jsonl"
    successful_count = (
        sum(row.get("judge_status") == "ok" for row in _score_rows(scores_path))
        if scores_path.is_file()
        else 0
    )
    if not tolerate_partial_failure or successful_count == 0:
        raise subprocess.CalledProcessError(process.returncode, process.args)


def _retry_response_judgments(
    *,
    assert_command: str,
    config: Path,
    suite: str,
    run_id: str,
    artifact_root: Path,
    run_root: Path,
) -> int:
    inference_path = run_root / "inference_set.jsonl"
    scores_path = run_root / "scores.jsonl"
    for attempt in range(1, MAX_JUDGE_RETRIES + 1):
        failures = _unjudged_case_count(inference_path, scores_path)
        if failures == 0:
            return attempt - 1
        print(f"Retrying {failures} missing or malformed response judgment(s), attempt {attempt}")
        _retain_successful_scores(scores_path)
        _run_judge_stage(
            assert_command=assert_command,
            config=config,
            suite=f"{suite}-response-retry",
            run_id=f"{run_id}-{attempt}",
            artifact_root=artifact_root,
            inference_set=inference_path,
            save_dir=run_root,
            force=False,
            tolerate_partial_failure=True,
        )
    remaining = _unjudged_case_count(inference_path, scores_path)
    if remaining:
        raise RuntimeError(
            f"{remaining} response judgment(s) remained incomplete after "
            f"{MAX_JUDGE_RETRIES} retries"
        )
    return MAX_JUDGE_RETRIES


def _retry_trace_judgments(
    *,
    assert_command: str,
    config: Path,
    suite: str,
    run_id: str,
    artifact_root: Path,
    trace_dir: Path,
) -> int:
    inference_path = trace_dir / "inference_set.jsonl"
    scores_path = trace_dir / "scores.jsonl"
    for attempt in range(1, MAX_JUDGE_RETRIES + 1):
        failures = _unjudged_case_count(inference_path, scores_path)
        if failures == 0:
            return attempt - 1
        print(f"Retrying trace judgments after {failures} malformed row(s), attempt {attempt}")
        _retain_successful_scores(scores_path)
        _run_judge_stage(
            assert_command=assert_command,
            config=config,
            suite=f"{suite}-trace-retry",
            run_id=f"{run_id}-{attempt}",
            artifact_root=artifact_root,
            inference_set=inference_path,
            save_dir=trace_dir,
            force=False,
            tolerate_partial_failure=True,
        )
    remaining = _unjudged_case_count(inference_path, scores_path)
    if remaining:
        raise RuntimeError(
            f"{remaining} trace judgment(s) remained incomplete after "
            f"{MAX_JUDGE_RETRIES} retries"
        )
    return MAX_JUDGE_RETRIES


def _is_recoverable_judge_failure(run_root: Path) -> bool:
    manifest_path = run_root / "manifest.json"
    if not manifest_path.is_file():
        return False
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    stages = manifest.get("stages")
    return (
        isinstance(stages, dict)
        and stages.get("inference") == "completed"
        and stages.get("judge") == "failed"
        and (run_root / "inference_set.jsonl").is_file()
        and (run_root / "scores.jsonl").is_file()
    )


def _record_judge_recovery(run_root: Path, retries: int) -> None:
    manifest_path = run_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    completed = datetime.now(UTC).isoformat()
    stages = manifest.setdefault("stages", {})
    if not isinstance(stages, dict):
        raise ValueError("ASSERT manifest stages must be an object")
    stages["judge"] = "completed"
    manifest["status"] = "completed"
    manifest["ended_at"] = completed
    manifest["heartbeat_at"] = completed
    manifest["judge_recovery"] = {
        "completed_at": completed,
        "retry_attempts": retries,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _trace_group_dimensions(path: Path) -> dict[str, dict[str, str]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    groups: dict[str, dict[str, Any]] = {}
    for resource in document.get("resourceSpans", []):
        for scope in resource.get("scopeSpans", []):
            for span in scope.get("spans", []):
                attributes = {
                    item.get("key"): next(iter(item.get("value", {}).values()), "")
                    for item in span.get("attributes", [])
                    if isinstance(item, dict)
                }
                session_id = str(attributes.get("session.id", "")).strip()
                if not session_id:
                    continue
                group = groups.setdefault(
                    session_id,
                    {
                        "spans": 0,
                        "errors": 0,
                        "turns": set(),
                        "case_ids": set(),
                        "response_ids": set(),
                        "run_ids": set(),
                        "fields": set(),
                    },
                )
                group["spans"] = int(group["spans"]) + 1
                if span.get("status", {}).get("code") == "STATUS_CODE_ERROR":
                    group["errors"] = int(group["errors"]) + 1
                for key, bucket in (
                    ("assert.turn_index", "turns"),
                    ("assert.case_id", "case_ids"),
                    ("assert.response_id", "response_ids"),
                    ("assert.run_id", "run_ids"),
                ):
                    value = str(attributes.get(key, "")).strip()
                    if value:
                        group[bucket].add(value)
                        group["fields"].add(key)
                group["fields"].add("session.id")
    return {
        session_id: {
            "trace_span_count": str(group["spans"]),
            "trace_error_span_count": str(group["errors"]),
            "trace_correlated_turn_count": str(len(group["turns"])),
            "trace_turn_indexes": ",".join(sorted(group["turns"])),
            "trace_case_id_count": str(len(group["case_ids"])),
            "trace_response_id_count": str(len(group["response_ids"])),
            "trace_run_id": ",".join(sorted(group["run_ids"])),
            "trace_correlation_fields": ",".join(sorted(group["fields"])),
        }
        for session_id, group in groups.items()
    }


def _normalize_trace_inference_set(path: Path, traces_path: Path | None = None) -> None:
    trace_dimensions = _trace_group_dimensions(traces_path) if traces_path is not None else {}
    normalized: list[dict[str, object]] = []
    case_ids: set[str] = set()
    for index, row in enumerate(_score_rows(path), start=1):
        metadata = row.get("metadata")
        if not isinstance(metadata, dict):
            raise ValueError(f"Trace inference row {index} is missing metadata")
        session_id = str(metadata.get("session_id", "")).strip()
        if not session_id:
            raise ValueError(f"Trace inference row {index} is missing session_id")
        case_id = f"trace-{session_id}"
        if case_id in case_ids:
            raise ValueError(f"Duplicate trace session_id: {session_id}")
        if traces_path is not None and session_id not in trace_dimensions:
            raise ValueError(
                f"Trace inference session has no OTLP correlation metadata: {session_id}"
            )
        events = row.get("events")
        if not isinstance(events, list):
            raise ValueError(f"Trace inference row {index} has invalid events")
        case_ids.add(case_id)
        normalized.append(
            {
                "type": "scenario",
                "test_case_id": case_id,
                "behavior": (
                    "Evaluate redacted telemetry evidence. Content-bearing attributes are "
                    "intentionally removed; use remaining events and content-free "
                    "correlation metadata."
                ),
                "events": events,
                "llm_calls": [],
                "stop_reason": "completed",
                "target": "bank-servicing-agent-trace",
                "tester_model": "",
                "target_reasoning_effort": None,
                "tester_reasoning_effort": None,
                "dimensions": {
                    "session_id": session_id,
                    "runtime_mode": str(metadata.get("runtime_mode", "")),
                    "trace_type": str(metadata.get("type", "")),
                    **trace_dimensions.get(session_id, {}),
                },
            }
        )
    path.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in normalized),
        encoding="utf-8",
    )


def _command_validate(_: argparse.Namespace) -> int:
    errors = validate_repository(_repository_root())
    if errors:
        for error in errors:
            print(error)
        return 1
    print("ASSERT configuration is valid.")
    return 0


def _command_preflight(args: argparse.Namespace) -> int:
    result = asyncio.run(run_preflight(args.output))
    print(json.dumps({"passed": result.passed, "timestamp": result.timestamp}))
    return 0


def _command_run(args: argparse.Namespace) -> int:
    run_id = args.run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    artifact_root = args.artifact_root.resolve()
    ledger = args.ledger or artifact_root / "results" / "correlation" / f"{run_id}.jsonl"
    preflight_output = args.preflight_output or (
        artifact_root / "results" / args.suite / run_id / "preflight.json"
    )
    os.environ["ASSERT_RUN_ID"] = run_id
    os.environ["ASSERT_CORRELATION_LEDGER"] = str(ledger)
    asyncio.run(run_preflight(preflight_output))
    environment = os.environ.copy()
    command = [
        args.assert_command,
        "run",
        "--config",
        str(args.config),
        "--override",
        f"suite={args.suite}",
        "--override",
        f"run={run_id}",
        "--override",
        f"artifacts_root={artifact_root}",
    ]
    process = subprocess.run(
        command,
        check=False,
        env=environment,
    )
    run_root = artifact_root / "results" / args.suite / run_id
    if process.returncode != 0 and not (
        getattr(args, "allow_judge_retry", False) and _is_recoverable_judge_failure(run_root)
    ):
        raise subprocess.CalledProcessError(process.returncode, process.args)
    print(
        json.dumps(
            {
                "run_id": run_id,
                "ledger": str(ledger),
                "run_root": str(run_root),
            }
        )
    )
    return 0


def _command_import(args: argparse.Namespace) -> int:
    result = query_and_import(
        workspace_id=args.workspace_id,
        ledger_path=args.ledger,
        output_directory=args.output,
        include_content=args.include_content,
    )
    print(
        json.dumps(
            {
                "complete": result.complete,
                "expected_turns": result.expected_turns,
                "correlated_turns": result.correlated_turns,
                "otlp_path": str(result.otlp_path),
            }
        )
    )
    return 0 if result.complete else 1


def _command_gate(args: argparse.Namespace) -> int:
    result = evaluate_gates(
        scores_path=args.scores,
        policy_path=args.policy,
        trace_completeness_path=args.trace_completeness,
        trace_scores_path=args.trace_scores,
        require_all_cases=args.require_all_cases,
    )
    write_gate_result(result, args.output)
    print(json.dumps({"passed": result.passed, "weighted_score": result.weighted_score}))
    return 0 if result.passed else 1


def _command_multisource(args: argparse.Namespace) -> int:
    run_id = args.run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    artifact_root = args.artifact_root.resolve()
    run_root = artifact_root / "results" / "multi-source-intro" / run_id
    os.environ["ASSERT_RUN_ID"] = run_id
    os.environ["ASSERT_CORRELATION_LEDGER"] = str(
        artifact_root / "results" / "correlation" / f"{run_id}.jsonl"
    )
    result = asyncio.run(
        run_multisource_case(
            run_root / "result.json",
            run_root / "summary.md",
        )
    )
    print(
        json.dumps(
            {
                "passed": result.passed,
                "hard_failure": result.hard_failure,
                "run_id": run_id,
                "run_root": str(run_root),
            }
        )
    )
    return 0 if result.passed else 1


def _command_live(args: argparse.Namespace) -> int:
    run_id = args.run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    artifact_root = args.artifact_root.resolve()
    run_root = artifact_root / "results" / args.suite / run_id
    ledger = artifact_root / "results" / "correlation" / f"{run_id}.jsonl"
    run_args = argparse.Namespace(
        config=args.config,
        suite=args.suite,
        run_id=run_id,
        assert_command=args.assert_command,
        ledger=ledger,
        preflight_output=run_root / "preflight.json",
        artifact_root=artifact_root,
        allow_judge_retry=True,
    )
    if args.resume:
        required = (run_root / "inference_set.jsonl", run_root / "scores.jsonl", ledger)
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise RuntimeError(f"Cannot resume ASSERT run; missing artifacts: {', '.join(missing)}")
    else:
        _command_run(run_args)
    response_retries = _retry_response_judgments(
        assert_command=args.assert_command,
        config=args.config,
        suite=args.suite,
        run_id=run_id,
        artifact_root=artifact_root,
        run_root=run_root,
    )
    _record_judge_recovery(run_root, response_retries)
    time.sleep(args.telemetry_delay)
    trace_result = query_and_import(
        workspace_id=args.workspace_id,
        ledger_path=ledger,
        output_directory=run_root / "trace-import",
        include_content=False,
    )
    if not trace_result.complete:
        raise RuntimeError("Trace correlation is incomplete")
    trace_dir = run_root / "trace-judge"
    trace_scores = trace_dir / "scores.jsonl"
    subprocess.run(
        [
            args.assert_command,
            "judge-traces",
            "--traces",
            str(trace_result.otlp_path),
            "--config",
            str(args.config),
            "--group-by",
            "session.id",
            "--output",
            str(trace_dir),
        ],
        check=True,
        env=os.environ.copy(),
    )
    _normalize_trace_inference_set(trace_dir / "inference_set.jsonl", trace_result.otlp_path)
    _run_judge_stage(
        assert_command=args.assert_command,
        config=args.config,
        suite=f"{args.suite}-traces",
        run_id=run_id,
        artifact_root=artifact_root,
        inference_set=trace_dir / "inference_set.jsonl",
        save_dir=trace_dir,
        force=True,
        tolerate_partial_failure=True,
    )
    _retry_trace_judgments(
        assert_command=args.assert_command,
        config=args.config,
        suite=args.suite,
        run_id=run_id,
        artifact_root=artifact_root,
        trace_dir=trace_dir,
    )
    result = evaluate_gates(
        scores_path=run_root / "scores.jsonl",
        policy_path=args.policy,
        trace_completeness_path=trace_result.completeness_path,
        trace_scores_path=trace_scores,
        require_all_cases=args.require_all_cases,
    )
    write_gate_result(result, run_root / "gate-result.json")
    print(
        json.dumps(
            {
                "passed": result.passed,
                "run_id": run_id,
                "run_root": str(run_root),
                "weighted_score": result.weighted_score,
            }
        )
    )
    return 0 if result.passed else 1


def build_parser() -> argparse.ArgumentParser:
    evaluation = _evaluation_root()
    parser = argparse.ArgumentParser(description="Run Bank Servicing Agent ASSERT beta evaluation")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate")
    validate.set_defaults(func=_command_validate)

    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--output", type=Path)
    preflight.set_defaults(func=_command_preflight)

    run = subparsers.add_parser("run")
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--suite", required=True)
    run.add_argument("--run-id")
    run.add_argument("--assert-command", default="assert-ai")
    run.add_argument("--ledger", type=Path)
    run.add_argument("--preflight-output", type=Path)
    run.add_argument("--artifact-root", type=Path, default=evaluation / "artifacts")
    run.set_defaults(func=_command_run)

    trace_import = subparsers.add_parser("import-traces")
    trace_import.add_argument("--workspace-id", required=True)
    trace_import.add_argument("--ledger", type=Path, required=True)
    trace_import.add_argument("--output", type=Path, required=True)
    trace_import.add_argument("--include-content", action="store_true")
    trace_import.set_defaults(func=_command_import)

    gate = subparsers.add_parser("gate")
    gate.add_argument("--scores", type=Path, required=True)
    gate.add_argument("--policy", type=Path, default=evaluation / "policies" / "rubric-policy.json")
    gate.add_argument("--trace-completeness", type=Path, required=True)
    gate.add_argument("--trace-scores", type=Path)
    gate.add_argument("--require-all-cases", type=int)
    gate.add_argument("--output", type=Path, required=True)
    gate.set_defaults(func=_command_gate)

    multisource = subparsers.add_parser("multisource")
    multisource.add_argument("--run-id")
    multisource.add_argument("--artifact-root", type=Path, default=evaluation / "artifacts")
    multisource.set_defaults(func=_command_multisource)

    live = subparsers.add_parser("live")
    live.add_argument("--config", type=Path, required=True)
    live.add_argument("--suite", required=True)
    live.add_argument("--run-id")
    live.add_argument("--assert-command", default="assert-ai")
    live.add_argument("--artifact-root", type=Path, default=evaluation / "artifacts")
    live.add_argument(
        "--workspace-id",
        default=os.getenv("APPLICATIONINSIGHTS_WORKSPACE_ID"),
        required=os.getenv("APPLICATIONINSIGHTS_WORKSPACE_ID") is None,
    )
    live.add_argument("--telemetry-delay", type=int, default=60)
    live.add_argument("--require-all-cases", type=int)
    live.add_argument("--resume", action="store_true")
    live.add_argument("--policy", type=Path, default=evaluation / "policies" / "rubric-policy.json")
    live.set_defaults(func=_command_live)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(args.func(args))
