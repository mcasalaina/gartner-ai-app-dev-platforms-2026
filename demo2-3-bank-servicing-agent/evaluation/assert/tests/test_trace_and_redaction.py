from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from bank_assert.redaction import redact
from bank_assert.trace_import import import_rows, normalize_rows


def record() -> dict[str, object]:
    return {
        "run_id": "run-1",
        "case_id": "case-1",
        "session_id": "74e2d046-49f1-4f55-b98f-836878771222",
        "turn_index": 1,
        "trace_id": "a" * 32,
        "parent_span_id": "b" * 16,
        "response_id": "response-1",
        "started_at": "2026-07-15T10:00:00+00:00",
        "completed_at": "2026-07-15T10:00:01+00:00",
    }


def test_normalizer_assigns_session_and_redacts_content() -> None:
    rows = [
        {
            "EventTime": datetime(2026, 7, 15, 10, 0, tzinfo=UTC),
            "OpId": "a" * 32,
            "Parent": "b" * 16,
            "Span": "c" * 16,
            "EventName": "invoke_agent",
            "Props": {
                "gen_ai.input.messages": "private prompt",
                "gen_ai.system_instructions": "private instructions",
                "gen_ai.tool.call.arguments": '{"customer":"private"}',
                "gen_ai.tool.call.result": '{"status":"private"}',
                "authorization": "Bearer secret-token",
                "salary": "$1234.56",
                "user": "person@example.com",
                "gen_ai.usage.input_tokens": "42",
            },
            "DurationMs": 10,
            "Success": True,
            "ResultCode": "200",
            "SourceTable": "AppRequests",
        }
    ]
    otlp, completeness = normalize_rows(rows, [record()])
    assert completeness["complete"] is True
    attributes = otlp["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["attributes"]
    attribute_map = {
        attribute["key"]: attribute["value"]["stringValue"]
        for attribute in attributes
        if "stringValue" in attribute["value"]
    }
    assert attribute_map["session.id"] == record()["session_id"]
    assert attribute_map["gen_ai.input.messages"] == "[REDACTED_CONTENT]"
    assert attribute_map["gen_ai.system_instructions"] == "[REDACTED_CONTENT]"
    assert attribute_map["gen_ai.tool.call.arguments"] == "[REDACTED_CONTENT]"
    assert attribute_map["gen_ai.tool.call.result"] == "[REDACTED_CONTENT]"
    assert attribute_map["authorization"] == "[REDACTED_SECRET]"
    assert attribute_map["user"] == "[REDACTED_EMAIL]"
    token_attribute = next(
        attribute for attribute in attributes if attribute["key"] == "gen_ai.usage.input_tokens"
    )
    assert token_attribute["value"] == {"intValue": "42"}


def test_missing_trace_marks_case_incomplete(tmp_path: Path) -> None:
    result = import_rows(rows=[], records=[record()], output_directory=tmp_path)
    assert result.complete is False
    assert result.expected_turns == 1
    assert result.correlated_turns == 0
    assert result.otlp_path.is_file()


def test_redactor_removes_tokens_email_and_salary_values() -> None:
    value = {
        "safe": "contact person@example.com about a $2500 payroll deposit",
        "detail": "Bearer abc.def.ghi",
        "client_secret": "do-not-keep",
    }
    result = redact(value)
    rendered = str(result)
    assert "person@example.com" not in rendered
    assert "Bearer abc" not in rendered
    assert "2500" not in rendered
    assert "do-not-keep" not in rendered
