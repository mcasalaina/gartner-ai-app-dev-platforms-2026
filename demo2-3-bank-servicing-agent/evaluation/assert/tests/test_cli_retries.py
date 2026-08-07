from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bank_assert import cli


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_unjudged_count_includes_missing_and_malformed_rows(tmp_path: Path) -> None:
    inference = tmp_path / "inference_set.jsonl"
    scores = tmp_path / "scores.jsonl"
    _write_jsonl(
        inference,
        [
            {"type": "prompt", "test_case_id": "one"},
            {"type": "prompt", "test_case_id": "two"},
            {"type": "scenario", "test_case_id": "three"},
        ],
    )
    _write_jsonl(
        scores,
        [
            {"type": "prompt", "test_case_id": "one", "judge_status": "ok"},
            {"type": "prompt", "test_case_id": "two", "judge_status": "judge_failed"},
        ],
    )

    assert cli._unjudged_case_count(inference, scores) == 2


def test_response_judge_retry_recovers_missing_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inference = tmp_path / "inference_set.jsonl"
    scores = tmp_path / "scores.jsonl"
    _write_jsonl(
        inference,
        [
            {"type": "prompt", "test_case_id": "one"},
            {"type": "scenario", "test_case_id": "two"},
        ],
    )
    _write_jsonl(
        scores,
        [{"type": "prompt", "test_case_id": "one", "judge_status": "judge_failed"}],
    )
    attempts: list[dict[str, Any]] = []

    def fake_judge(**kwargs: Any) -> None:
        attempts.append(kwargs)
        _write_jsonl(
            scores,
            [
                {"type": "prompt", "test_case_id": "one", "judge_status": "ok"},
                {"type": "scenario", "test_case_id": "two", "judge_status": "ok"},
            ],
        )

    monkeypatch.setattr(cli, "_run_judge_stage", fake_judge)

    retries = cli._retry_response_judgments(
        assert_command="assert-ai",
        config=tmp_path / "config.yaml",
        suite="suite",
        run_id="run",
        artifact_root=tmp_path,
        run_root=tmp_path,
    )

    assert retries == 1
    assert len(attempts) == 1
    assert attempts[0]["tolerate_partial_failure"] is True


def test_response_judge_retry_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inference = tmp_path / "inference_set.jsonl"
    scores = tmp_path / "scores.jsonl"
    _write_jsonl(
        inference,
        [
            {"type": "prompt", "test_case_id": "one"},
            {"type": "prompt", "test_case_id": "two"},
        ],
    )
    _write_jsonl(
        scores,
        [{"type": "prompt", "test_case_id": "one", "judge_status": "ok"}],
    )
    monkeypatch.setattr(cli, "MAX_JUDGE_RETRIES", 2)
    monkeypatch.setattr(cli, "_run_judge_stage", lambda **_: None)

    with pytest.raises(RuntimeError, match="remained incomplete"):
        cli._retry_response_judgments(
            assert_command="assert-ai",
            config=tmp_path / "config.yaml",
            suite="suite",
            run_id="run",
            artifact_root=tmp_path,
            run_root=tmp_path,
        )


def test_partial_judge_failure_is_retryable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scores = tmp_path / "scores.jsonl"
    _write_jsonl(
        scores,
        [{"type": "prompt", "test_case_id": "one", "judge_status": "ok"}],
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, args=["assert-ai"]),
    )

    cli._run_judge_stage(
        assert_command="assert-ai",
        config=tmp_path / "config.yaml",
        suite="suite",
        run_id="run",
        artifact_root=tmp_path,
        inference_set=tmp_path / "inference_set.jsonl",
        save_dir=tmp_path,
        force=False,
        tolerate_partial_failure=True,
    )


def test_recoverable_failure_requires_completed_inference(tmp_path: Path) -> None:
    _write_jsonl(tmp_path / "inference_set.jsonl", [])
    _write_jsonl(tmp_path / "scores.jsonl", [])
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "status": "failed",
                "stages": {"inference": "completed", "judge": "failed"},
            }
        ),
        encoding="utf-8",
    )

    assert cli._is_recoverable_judge_failure(tmp_path)


def test_resume_fails_closed_when_run_artifacts_are_missing(tmp_path: Path) -> None:
    args = SimpleNamespace(
        run_id="run",
        artifact_root=tmp_path,
        suite="suite",
        config=tmp_path / "config.yaml",
        assert_command="assert-ai",
        resume=True,
    )

    with pytest.raises(RuntimeError, match="missing artifacts"):
        cli._command_live(args)


def test_normalize_trace_inference_set_adds_unified_case_identity(tmp_path: Path) -> None:
    inference_path = tmp_path / "inference_set.jsonl"
    traces_path = tmp_path / "traces.otlp.json"
    events = [{"actor": "target", "edit": {"type": "add_message", "message": "[REDACTED]"}}]
    _write_jsonl(
        inference_path,
        [
            {
                "events": events,
                "metadata": {
                    "type": "otel_import",
                    "session_id": "session-1",
                    "runtime_mode": "otel_traced",
                },
                "raw": {"resourceSpans": []},
            }
        ],
    )
    traces_path.write_text(
        json.dumps(
            {
                "resourceSpans": [
                    {
                        "scopeSpans": [
                            {
                                "spans": [
                                    {
                                        "attributes": [
                                            {
                                                "key": "session.id",
                                                "value": {"stringValue": "session-1"},
                                            },
                                            {
                                                "key": "assert.run_id",
                                                "value": {"stringValue": "run-1"},
                                            },
                                            {
                                                "key": "assert.case_id",
                                                "value": {"stringValue": "case-1"},
                                            },
                                            {
                                                "key": "assert.response_id",
                                                "value": {"stringValue": "response-1"},
                                            },
                                            {
                                                "key": "assert.turn_index",
                                                "value": {"intValue": "1"},
                                            },
                                        ],
                                        "status": {"code": "STATUS_CODE_OK"},
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    cli._normalize_trace_inference_set(inference_path, traces_path)

    rows = [json.loads(line) for line in inference_path.read_text().splitlines()]
    assert rows == [
        {
            "type": "scenario",
            "test_case_id": "trace-session-1",
            "behavior": (
                "Evaluate redacted telemetry evidence. Content-bearing attributes are "
                "intentionally removed; use remaining events and content-free correlation metadata."
            ),
            "events": events,
            "llm_calls": [],
            "stop_reason": "completed",
            "target": "bank-servicing-agent-trace",
            "tester_model": "",
            "target_reasoning_effort": None,
            "tester_reasoning_effort": None,
            "dimensions": {
                "session_id": "session-1",
                "runtime_mode": "otel_traced",
                "trace_type": "otel_import",
                "trace_span_count": "1",
                "trace_error_span_count": "0",
                "trace_correlated_turn_count": "1",
                "trace_turn_indexes": "1",
                "trace_case_id_count": "1",
                "trace_response_id_count": "1",
                "trace_run_id": "run-1",
                "trace_correlation_fields": (
                    "assert.case_id,assert.response_id,assert.run_id,"
                    "assert.turn_index,session.id"
                ),
            },
        }
    ]


@pytest.mark.parametrize(
    ("row", "message"),
    [
        ({"events": []}, "missing metadata"),
        ({"events": [], "metadata": {}}, "missing session_id"),
        ({"events": {}, "metadata": {"session_id": "session-1"}}, "invalid events"),
    ],
)
def test_normalize_trace_inference_set_rejects_invalid_rows(
    tmp_path: Path, row: dict[str, object], message: str
) -> None:
    inference_path = tmp_path / "inference_set.jsonl"
    _write_jsonl(inference_path, [row])

    with pytest.raises(ValueError, match=message):
        cli._normalize_trace_inference_set(inference_path)
