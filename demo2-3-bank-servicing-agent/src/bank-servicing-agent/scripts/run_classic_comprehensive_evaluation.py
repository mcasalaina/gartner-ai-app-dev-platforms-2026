from __future__ import annotations

import argparse
from collections.abc import Mapping
from collections import defaultdict
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import secrets
import subprocess
import time
from typing import Any

import yaml
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import TestingCriterionAzureAIEvaluator
from azure.identity import AzureCliCredential
from openai import APIError, OpenAI
from openai.types.eval_create_params import DataSourceConfigCustom
from openai.types.evals.create_eval_jsonl_run_data_source_param import (
    CreateEvalJSONLRunDataSourceParam,
    SourceFileContent,
    SourceFileContentContent,
)


TERMINAL_STATES = {"completed", "failed", "cancelled", "canceled"}
PROHIBITED_INPUT_TERMS = ("synthetic", "demo")
REQUESTED_METRICS = {
    "groundedness",
    "relevance",
    "fluency",
    "task_completion",
    "task_adherence",
    "intent_resolution",
    "tool_call_accuracy",
    "tool_selection",
    "tool_input_accuracy",
    "tool_output_utilization",
    "tool_call_success",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-endpoint", required=True)
    parser.add_argument("--agent-name", default="bank-servicing-agent")
    parser.add_argument("--agent-version", required=True)
    parser.add_argument("--model", default="gpt-5.4-mini")
    parser.add_argument("--api-version", default="v1")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--resume-directory", type=Path)
    parser.add_argument("--reuse-invocations", type=Path)
    parser.add_argument("--trace-only", action="store_true")
    parser.add_argument("--workspace-id")
    parser.add_argument("--trace-ingestion-wait-seconds", type=int, default=180)
    return parser.parse_args()


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(cases) != 20:
        raise ValueError(f"Expected exactly 20 evaluation inputs, found {len(cases)}")
    for case in cases:
        query = str(case.get("query") or "")
        prohibited = [term for term in PROHIBITED_INPUT_TERMS if term in query.lower()]
        if prohibited:
            raise ValueError(
                f"{case.get('case_id', '<unknown>')} contains prohibited input terms: "
                f"{', '.join(prohibited)}"
            )
    return cases


def response_text(response: Any) -> str:
    text = getattr(response, "output_text", "")
    if text:
        return str(text)
    parts: list[str] = []
    for item in getattr(response, "output", []):
        if getattr(item, "type", None) != "message":
            continue
        for content in getattr(item, "content", []):
            if getattr(content, "type", None) == "output_text":
                parts.append(str(content.text))
    return "\n".join(parts)


def invoke_cases(
    client: OpenAI,
    *,
    cases: list[dict[str, Any]],
    model: str,
    agent_version: str,
    run_id: str,
    checkpoint_path: Path,
    existing_invocations: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    invocations = list(existing_invocations or [])
    checkpoint_changed = False
    for invocation in invocations:
        if invocation.get("agent_version") != agent_version:
            invocation["agent_version"] = agent_version
            checkpoint_changed = True
    if invocations and (checkpoint_changed or not checkpoint_path.is_file()):
        checkpoint_path.write_text(
            json.dumps(invocations, indent=2) + "\n",
            encoding="utf-8",
        )
    completed_case_ids = {str(item["case_id"]) for item in invocations}
    for index, case in enumerate(cases, start=1):
        if str(case["case_id"]) in completed_case_ids:
            continue
        trace_id = secrets.token_hex(16)
        span_id = secrets.token_hex(8)
        started_at = datetime.now(UTC).isoformat()
        response = None
        for attempt in range(1, 4):
            try:
                response = client.responses.create(
                    model=model,
                    input=[{"role": "user", "content": str(case["query"])}],
                    extra_headers={
                        "x-client-demo-mode": str(case["mode"]),
                        "x-ms-agent-version": agent_version,
                        "traceparent": f"00-{trace_id}-{span_id}-01",
                        "baggage": (
                            f"evaluation.run_id={run_id},"
                            f"evaluation.case_id={case['case_id']}"
                        ),
                    },
                )
                break
            except APIError:
                if attempt == 3:
                    raise
                time.sleep(10 * attempt)
        if response is None:
            raise RuntimeError(f"{case['case_id']} did not return a response")
        text = response_text(response)
        if not text:
            raise RuntimeError(f"{case['case_id']} returned no assistant text")
        invocations.append(
            {
                **case,
                "trace_id": trace_id,
                "agent_version": agent_version,
                "response_id": str(response.id),
                "response": text,
                "started_at": started_at,
                "completed_at": datetime.now(UTC).isoformat(),
            }
        )
        checkpoint_path.write_text(
            json.dumps(invocations, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Invoked {index:02d}/20: {case['case_id']}", flush=True)
    return invocations


def criterion(
    name: str,
    *,
    model: str,
    data_mapping: dict[str, str],
) -> TestingCriterionAzureAIEvaluator:
    return TestingCriterionAzureAIEvaluator(
        type="azure_ai_evaluator",
        name=name,
        evaluator_name=f"builtin.{name}",
        initialization_parameters={"model": model},
        data_mapping=data_mapping,
    )


def response_quality_criteria(model: str) -> list[TestingCriterionAzureAIEvaluator]:
    mapping = {
        "query": "{{item.query}}",
        "response": "{{item.response}}",
    }
    return [
        criterion("relevance", model=model, data_mapping=mapping),
        criterion("fluency", model=model, data_mapping=mapping),
    ]


def agent_outcome_criteria(model: str) -> list[TestingCriterionAzureAIEvaluator]:
    conversation_mapping = {
        "messages": "{{item.messages}}",
        "tool_definitions": "{{item.tool_definitions}}",
    }
    return [
        criterion("groundedness", model=model, data_mapping=conversation_mapping),
        criterion("task_completion", model=model, data_mapping=conversation_mapping),
        criterion("task_adherence", model=model, data_mapping=conversation_mapping),
    ]


def intent_resolution_criteria(model: str) -> list[TestingCriterionAzureAIEvaluator]:
    return [
        criterion(
            "intent_resolution",
            model=model,
            data_mapping={
                "query": "{{item.query}}",
                "response": "{{item.response}}",
                "tool_definitions": "{{item.tool_definitions}}",
            },
        ),
    ]


def tool_quality_criteria(model: str) -> list[TestingCriterionAzureAIEvaluator]:
    full_mapping = {
        "query": "{{item.query}}",
        "response": "{{item.response}}",
        "tool_definitions": "{{item.tool_definitions}}",
    }
    return [
        criterion("tool_call_accuracy", model=model, data_mapping=full_mapping),
        criterion("tool_selection", model=model, data_mapping=full_mapping),
        criterion("tool_input_accuracy", model=model, data_mapping=full_mapping),
        criterion("tool_output_utilization", model=model, data_mapping=full_mapping),
        criterion(
            "tool_call_success",
            model=model,
            data_mapping={
                "response": "{{item.response}}",
                "tool_definitions": "{{item.tool_definitions}}",
            },
        ),
    ]


def unified_standard_criteria(
    model: str,
) -> list[TestingCriterionAzureAIEvaluator]:
    text_mapping = {
        "query": "{{item.quality_query}}",
        "response": "{{item.quality_response}}",
    }
    conversation_mapping = {
        "messages": "{{item.conversation_messages}}",
        "tool_definitions": "{{item.available_tools}}",
    }
    tool_mapping = {
        "query": "{{item.query_messages}}",
        "response": "{{item.response_messages}}",
        "tool_definitions": "{{item.available_tools}}",
    }
    return [
        criterion("groundedness", model=model, data_mapping=conversation_mapping),
        criterion("relevance", model=model, data_mapping=text_mapping),
        criterion("fluency", model=model, data_mapping=text_mapping),
        criterion("task_completion", model=model, data_mapping=conversation_mapping),
        criterion("task_adherence", model=model, data_mapping=conversation_mapping),
        criterion("intent_resolution", model=model, data_mapping=tool_mapping),
        criterion("tool_call_accuracy", model=model, data_mapping=tool_mapping),
        criterion("tool_selection", model=model, data_mapping=tool_mapping),
        criterion("tool_input_accuracy", model=model, data_mapping=tool_mapping),
        criterion("tool_output_utilization", model=model, data_mapping=tool_mapping),
        criterion(
            "tool_call_success",
            model=model,
            data_mapping={
                "response": "{{item.response_messages}}",
                "tool_definitions": "{{item.available_tools}}",
            },
        ),
    ]


def wait_for_run(client: Any, *, eval_id: str, run: Any) -> Any:
    while str(run.status) not in TERMINAL_STATES:
        time.sleep(10)
        run = client.evals.runs.retrieve(run_id=run.id, eval_id=eval_id)
    return run


def output_items(client: Any, *, eval_id: str, run_id: str) -> list[dict[str, Any]]:
    return [
        item.model_dump()
        for item in client.evals.runs.output_items.list(
            run_id=run_id,
            eval_id=eval_id,
        )
    ]


def run_response_quality_eval(
    client: Any,
    *,
    model: str,
    invocations: list[dict[str, Any]],
    timestamp: str,
) -> dict[str, Any]:
    evaluation = client.evals.create(
        name=f"bank-servicing-classic-response-quality-{timestamp}",
        data_source_config=DataSourceConfigCustom(
            type="custom",
            item_schema={
                "type": "object",
                "properties": {
                    "case_id": {"type": "string"},
                    "query": {"type": "string"},
                    "response": {"type": "string"},
                },
                "required": ["case_id", "query", "response"],
            },
            include_sample_schema=False,
        ),
        testing_criteria=response_quality_criteria(model),
    )
    rows = [
        {
            "case_id": item["case_id"],
            "query": item["query"],
            "response": item["response"],
        }
        for item in invocations
    ]
    run = client.evals.runs.create(
        eval_id=evaluation.id,
        name=f"response-quality-{timestamp}",
        data_source=CreateEvalJSONLRunDataSourceParam(
            type="jsonl",
            source=SourceFileContent(
                type="file_content",
                content=[SourceFileContentContent(item=row) for row in rows],
            ),
        ),
    )
    run = wait_for_run(client, eval_id=evaluation.id, run=run)
    return {
        "evaluation": client.evals.retrieve(evaluation.id).model_dump(),
        "run": run.model_dump(),
        "output_items": output_items(client, eval_id=evaluation.id, run_id=run.id),
    }


def run_trace_eval(
    client: Any,
    *,
    name: str,
    criteria: list[TestingCriterionAzureAIEvaluator],
    trace_ids: list[str],
    timestamp: str,
) -> dict[str, Any]:
    evaluation = client.evals.create(
        name=f"bank-servicing-classic-{name}-{timestamp}",
        data_source_config={
            "type": "azure_ai_source",
            "scenario": "traces",
        },
        testing_criteria=criteria,
    )
    run = client.evals.runs.create(
        eval_id=evaluation.id,
        name=f"{name}-{timestamp}",
        data_source={
            "type": "azure_ai_trace_data_source_preview",
            "trace_source": {
                "type": "trace_id_source",
                "trace_ids": trace_ids,
            },
        },
        extra_body={"evaluation_level": "conversation"},
    )
    run = wait_for_run(client, eval_id=evaluation.id, run=run)
    return {
        "evaluation": client.evals.retrieve(evaluation.id).model_dump(),
        "run": run.model_dump(),
        "output_items": output_items(client, eval_id=evaluation.id, run_id=run.id),
    }


def query_trace_rows(
    *,
    workspace_id: str,
    invocations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    trace_ids = ", ".join(
        json.dumps(str(item["trace_id"])) for item in invocations
    )
    query = f"""
union withsource=SourceTable AppDependencies, AppRequests
| where OperationId in ({trace_ids})
| extend Operation=tostring(Properties["gen_ai.operation.name"]),
         Input=tostring(Properties["gen_ai.input.messages"]),
         Output=tostring(Properties["gen_ai.output.messages"]),
         Tool=tostring(Properties["gen_ai.tool.name"]),
         CallId=tostring(Properties["gen_ai.tool.call.id"]),
         Arguments=tostring(Properties["gen_ai.tool.call.arguments"]),
         Result=tostring(Properties["gen_ai.tool.call.result"]),
         Description=tostring(Properties["gen_ai.tool.description"])
| where Operation in ("invoke_agent", "execute_tool")
| project EventTime=TimeGenerated, OperationId, SourceTable, Name, Success,
          Operation, Input, Output, Tool, CallId, Arguments, Result, Description
| order by EventTime asc
""".strip()
    start = min(
        datetime.fromisoformat(str(item["started_at"])) for item in invocations
    ) - timedelta(minutes=5)
    end = max(
        datetime.fromisoformat(str(item["completed_at"])) for item in invocations
    ) + timedelta(minutes=10)
    completed = subprocess.run(
        [
            "az",
            "monitor",
            "log-analytics",
            "query",
            "--workspace",
            workspace_id,
            "--analytics-query",
            query,
            "--timespan",
            f"{start.isoformat()}/{end.isoformat()}",
            "--output",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    rows = json.loads(completed.stdout)
    if not isinstance(rows, list):
        raise RuntimeError("Log Analytics query did not return a row array")
    return rows


def _json_value(value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _json_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"


def build_materialized_conversations(
    *,
    invocations: list[dict[str, Any]],
    trace_rows: list[dict[str, Any]],
    instructions: str,
) -> list[dict[str, Any]]:
    rows_by_trace: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in trace_rows:
        rows_by_trace[str(row.get("OperationId") or "")].append(row)

    observed_tools: dict[str, dict[str, Any]] = {}
    for row in trace_rows:
        tool_name = str(row.get("Tool") or "")
        call_id = str(row.get("CallId") or "")
        if not tool_name or not call_id:
            continue
        arguments = _json_value(row.get("Arguments"))
        properties = (
            {
                key: {"type": _json_type(value)}
                for key, value in arguments.items()
            }
            if isinstance(arguments, Mapping)
            else {}
        )
        tool = observed_tools.setdefault(
            tool_name,
            {
                "name": tool_name,
                "description": str(row.get("Description") or tool_name),
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        )
        parameters = tool["parameters"]
        parameters["properties"].update(properties)
        parameters["required"] = sorted(
            set(parameters["required"]) | set(properties)
        )
    tool_definitions = list(observed_tools.values())
    if not tool_definitions:
        raise RuntimeError("No tool definitions were found in the correlated traces")

    conversations: list[dict[str, Any]] = []
    for invocation in invocations:
        trace_id = str(invocation["trace_id"])
        query = [
            {"role": "system", "content": instructions},
            {"role": "user", "content": str(invocation["query"])},
        ]
        response: list[dict[str, Any]] = []
        for row in rows_by_trace.get(trace_id, []):
            tool_name = str(row.get("Tool") or "")
            call_id = str(row.get("CallId") or "")
            if str(row.get("Operation") or "") != "execute_tool" or not call_id:
                continue
            response.extend(
                [
                    {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_call",
                                "tool_call_id": call_id,
                                "name": tool_name,
                                "arguments": _json_value(row.get("Arguments")),
                            }
                        ],
                    },
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_call_id": call_id,
                                "tool_result": _json_value(row.get("Result")),
                            }
                        ],
                    },
                ]
            )
        response.append(
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": str(invocation["response"])}
                ],
            }
        )
        conversations.append(
            {
                "case_id": invocation["case_id"],
                "query": query,
                "response": response,
                "messages": [*query, *response],
                "tool_definitions": tool_definitions,
                "quality_query": str(invocation["query"]),
                "quality_response": str(invocation["response"]),
                "query_messages": query,
                "response_messages": response,
                "conversation_messages": [*query, *response],
                "available_tools": tool_definitions,
                "expected_behavior": invocation["expected_behavior"],
            }
        )
    return conversations


def run_materialized_eval(
    client: Any,
    *,
    name: str,
    criteria: list[TestingCriterionAzureAIEvaluator],
    conversations: list[dict[str, Any]],
    timestamp: str,
    fields: tuple[str, ...],
) -> dict[str, Any]:
    field_types = {
        "case_id": "string",
        "query": "array",
        "response": "array",
        "messages": "array",
        "tool_definitions": "array",
        "quality_query": "string",
        "quality_response": "string",
        "query_messages": "array",
        "response_messages": "array",
        "conversation_messages": "array",
        "available_tools": "array",
        "expected_behavior": "string",
    }
    items = [
        {field: conversation[field] for field in fields}
        for conversation in conversations
    ]
    evaluation = client.evals.create(
        name=f"bank-servicing-classic-{name}-{timestamp}",
        data_source_config=DataSourceConfigCustom(
            type="custom",
            item_schema={
                "type": "object",
                "properties": {
                    field: {"type": field_types[field]} for field in fields
                },
                "required": list(fields),
            },
            include_sample_schema=False,
        ),
        testing_criteria=criteria,
    )
    run = client.evals.runs.create(
        eval_id=evaluation.id,
        name=f"{name}-{timestamp}",
        data_source=CreateEvalJSONLRunDataSourceParam(
            type="jsonl",
            source=SourceFileContent(
                type="file_content",
                content=[
                    SourceFileContentContent(item=item)
                    for item in items
                ],
            ),
        ),
    )
    run = wait_for_run(client, eval_id=evaluation.id, run=run)
    return {
        "evaluation": client.evals.retrieve(evaluation.id).model_dump(),
        "run": run.model_dump(),
        "output_items": output_items(client, eval_id=evaluation.id, run_id=run.id),
    }


def metric_summary(runs: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for payload in runs.values():
        for item in payload["output_items"]:
            for result in item.get("results", []):
                name = str(result.get("metric") or result.get("name") or "unknown")
                entry = summary.setdefault(
                    name,
                    {"scores": [], "passed": 0, "failed": 0, "errored": 0},
                )
                score = result.get("score")
                if isinstance(score, (int, float)):
                    entry["scores"].append(float(score))
                if result.get("passed") is True:
                    entry["passed"] += 1
                elif result.get("passed") is False:
                    entry["failed"] += 1
                if result.get("status") == "error":
                    entry["errored"] += 1
    for entry in summary.values():
        scores = entry.pop("scores")
        entry["meanScore"] = sum(scores) / len(scores) if scores else None
    return summary


def failure_clusters(runs: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run_name, payload in runs.items():
        for item in payload["output_items"]:
            source = item.get("datasource_item") or {}
            case_id = source.get("case_id") or item.get("id")
            for result in item.get("results", []):
                if result.get("passed") is True and result.get("status") != "error":
                    continue
                metric = str(result.get("metric") or result.get("name") or "unknown")
                clusters[metric].append(
                    {
                        "run": run_name,
                        "caseId": case_id,
                        "passed": result.get("passed"),
                        "status": result.get("status"),
                        "reason": result.get("reason"),
                    }
                )
    return dict(clusters)


def evaluation_issues(
    runs: dict[str, dict[str, Any]],
    metrics: dict[str, dict[str, Any]],
    *,
    expected_items: int,
) -> list[str]:
    issues: list[str] = []
    for name, payload in runs.items():
        status = str(payload["run"].get("status"))
        if status != "completed":
            issues.append(f"{name} run status is {status}")
        item_count = len(payload["output_items"])
        if item_count != expected_items:
            issues.append(
                f"{name} returned {item_count} output items; expected {expected_items}"
            )
    missing_metrics = sorted(REQUESTED_METRICS - set(metrics))
    if missing_metrics:
        issues.append(f"missing metrics: {', '.join(missing_metrics)}")
    errored_metrics = sorted(
        name for name, values in metrics.items() if values["errored"]
    )
    if errored_metrics:
        issues.append(f"metrics contain evaluator errors: {', '.join(errored_metrics)}")
    return issues


def write_summary(
    path: Path,
    *,
    agent_version: str,
    invocations: list[dict[str, Any]],
    runs: dict[str, dict[str, Any]],
    metrics: dict[str, dict[str, Any]],
    clusters: dict[str, list[dict[str, Any]]],
) -> None:
    rows = []
    for name, values in sorted(metrics.items()):
        mean = values["meanScore"]
        rows.append(
            f"| {name} | {'n/a' if mean is None else f'{mean:.3f}'} | "
            f"{values['passed']} | {values['failed']} | {values['errored']} |"
        )
    run_rows = []
    for name, payload in runs.items():
        run = payload["run"]
        run_rows.append(
            f"| {name} | `{run.get('id')}` | {run.get('status')} | "
            f"{len(payload['output_items'])} |"
        )
    cluster_rows = [
        f"| {name} | {len(items)} |"
        for name, items in sorted(clusters.items())
    ]
    path.write_text(
        "\n".join(
            [
                "# Classic Foundry comprehensive evaluation",
                "",
                f"- Agent: `bank-servicing-agent` version `{agent_version}`",
                f"- Inputs: {len(invocations)} realistic, read-only banking requests",
                (
                    "- Execution: one classic Foundry evaluation run with all "
                    "requested built-in evaluators"
                ),
                (
                    "- Tool evaluator pass/fail counts include only applicable cases; "
                    "each run still contains all 20 output items."
                ),
                "",
                "| Evaluation | Run ID | Status | Output items |",
                "| --- | --- | --- | ---: |",
                *run_rows,
                "",
                "| Evaluator | Mean score | Passed | Failed | Errored |",
                "| --- | ---: | ---: | ---: | ---: |",
                *rows,
                "",
                "## Failure clusters",
                "",
                "| Evaluator | Non-passing or incomplete results |",
                "| --- | ---: |",
                *(cluster_rows or ["| none | 0 |"]),
                "",
            ]
        ),
        encoding="utf-8",
    )


def update_metadata(
    path: Path,
    *,
    agent_version: str,
    completed_at: str,
    result_dir: Path,
    runs: dict[str, dict[str, Any]],
    complete: bool,
) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    environment = data["environments"][data["defaultEnvironment"]]
    environment["lastClassicEval"] = {
        "agentVersion": agent_version,
        "completedAt": completed_at,
        "status": (
            "completed" if complete else "failed"
        ),
        "resultDirectory": str(result_dir.relative_to(path.parent)),
        "runs": {
            name: {
                "evalId": payload["evaluation"]["id"],
                "evalRunId": payload["run"]["id"],
                "status": str(payload["run"].get("status")),
                "reportUrl": str(payload["run"].get("report_url") or ""),
            }
            for name, payload in runs.items()
        },
    }
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def main() -> None:
    args = parse_args()
    cases = load_cases(args.dataset)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    if args.resume_directory:
        result_dir = args.resume_directory
        run_id = result_dir.name
        timestamp = run_id.removeprefix("classic-comprehensive-")
    else:
        run_id = f"classic-comprehensive-{timestamp}"
        result_dir = args.results_root / run_id
        result_dir.mkdir(parents=True, exist_ok=False)
    invocations_file = result_dir / "invocations.json"
    existing_invocations = (
        json.loads(invocations_file.read_text(encoding="utf-8"))
        if invocations_file.is_file()
        else json.loads(args.reuse_invocations.read_text(encoding="utf-8"))
        if args.reuse_invocations
        else []
    )

    with AzureCliCredential() as credential:
        token = credential.get_token("https://ai.azure.com/.default").token
        agent_client = OpenAI(
            api_key=token,
            base_url=(
                f"{args.project_endpoint.rstrip('/')}/agents/{args.agent_name}"
                "/endpoint/protocols/openai"
            ),
            default_query={"api-version": args.api_version},
            timeout=360,
            max_retries=2,
        )
        try:
            invocations = invoke_cases(
                agent_client,
                cases=cases,
                model=args.model,
                agent_version=args.agent_version,
                run_id=run_id,
                checkpoint_path=invocations_file,
                existing_invocations=existing_invocations,
            )
        finally:
            agent_client.close()

        print(
            f"Waiting {args.trace_ingestion_wait_seconds}s for trace ingestion",
            flush=True,
        )
        time.sleep(args.trace_ingestion_wait_seconds)
        conversations = None
        if args.workspace_id:
            trace_rows = query_trace_rows(
                workspace_id=args.workspace_id,
                invocations=invocations,
            )
            instructions = (
                Path(__file__).resolve().parents[1] / "instructions.md"
            ).read_text(encoding="utf-8")
            conversations = build_materialized_conversations(
                invocations=invocations,
                trace_rows=trace_rows,
                instructions=instructions,
            )

        with AIProjectClient(
            endpoint=args.project_endpoint,
            credential=credential,
        ) as project:
            with project.get_openai_client() as client:
                if conversations is not None:
                    standard_comprehensive = run_materialized_eval(
                        client,
                        name="standard-comprehensive",
                        criteria=unified_standard_criteria(args.model),
                        conversations=conversations,
                        timestamp=timestamp,
                        fields=(
                            "case_id",
                            "quality_query",
                            "quality_response",
                            "query_messages",
                            "response_messages",
                            "conversation_messages",
                            "available_tools",
                        ),
                    )
                else:
                    standard_comprehensive = run_trace_eval(
                        client,
                        name="standard-comprehensive",
                        criteria=unified_standard_criteria(args.model),
                        trace_ids=[item["trace_id"] for item in invocations],
                        timestamp=timestamp,
                    )
                runs = {"standard-comprehensive": standard_comprehensive}

    for name, payload in runs.items():
        (result_dir / f"{name}.json").write_text(
            json.dumps(payload, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
    metrics = metric_summary(runs)
    issues = evaluation_issues(runs, metrics, expected_items=len(invocations))
    clusters = failure_clusters(runs)
    (result_dir / "failure-clusters.json").write_text(
        json.dumps(clusters, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    summary_file = result_dir / "summary.md"
    write_summary(
        summary_file,
        agent_version=args.agent_version,
        invocations=invocations,
        runs=runs,
        metrics=metrics,
        clusters=clusters,
    )
    update_metadata(
        args.metadata,
        agent_version=args.agent_version,
        completed_at=datetime.now(UTC).isoformat(),
        result_dir=result_dir,
        runs=runs,
        complete=not issues,
    )
    print(
        json.dumps(
            {
                "status": "completed" if not issues else "incomplete",
                "resultDirectory": str(result_dir),
                "summaryFile": str(summary_file),
                "metrics": metrics,
                "issues": issues,
                "failureClusters": {
                    name: len(items) for name, items in clusters.items()
                },
            },
            indent=2,
        )
    )
    if issues:
        raise RuntimeError("; ".join(issues))


if __name__ == "__main__":
    main()
