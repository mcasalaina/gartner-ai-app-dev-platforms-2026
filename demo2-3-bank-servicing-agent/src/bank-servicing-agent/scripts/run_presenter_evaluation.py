from __future__ import annotations

import argparse
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    EvaluatorCategory,
    EvaluatorDefinitionType,
    RubricBasedEvaluatorDefinition,
    TestingCriterionAzureAIEvaluator,
)
from azure.identity import AzureCliCredential
from openai import OpenAI
from openai.types.eval_create_params import DataSourceConfigCustom
from openai.types.evals.create_eval_jsonl_run_data_source_param import (
    CreateEvalJSONLRunDataSourceParam,
    SourceFileContent,
    SourceFileContentContent,
)

SOURCE_LINE = re.compile(r"(?im)^Sources used:\s*(.+?)\s*$")
QUERIED_LINE = re.compile(r"(?im)^IQ services queried:\s*(.+?)\s*$")
SOURCE_FOOTER = re.compile(
    r"(?im)^(?:IQ services queried|Sources used):\s*.*(?:\n|$)"
)
TERMINAL_STATES = {"completed", "failed", "cancelled", "canceled"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-endpoint", required=True)
    parser.add_argument("--agent-name", default="bank-servicing-agent")
    parser.add_argument("--agent-version", required=True)
    parser.add_argument("--model", default="gpt-5.4-mini")
    parser.add_argument("--api-version", default="v1")
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--rubric", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, action="append", required=True)
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--reuse-invocations", type=Path)
    return parser.parse_args()


def load_cases(paths: list[Path]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                cases.append(json.loads(line))
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


def source_metadata(text: str) -> tuple[str, str, str]:
    queried_match = QUERIED_LINE.search(text)
    returned_match = SOURCE_LINE.search(text)
    queried = queried_match.group(1).strip() if queried_match else "none"
    returned = returned_match.group(1).strip() if returned_match else "none"
    visible_text = SOURCE_FOOTER.sub("", text).strip()
    return queried, returned, visible_text


def invoke_case(
    client: OpenAI,
    *,
    case: dict[str, Any],
    model: str,
    version: str,
) -> dict[str, Any]:
    headers = {
        "x-client-demo-mode": str(case["mode"]),
        "x-ms-agent-version": version,
    }
    response = client.responses.create(
        model=model,
        input=[{"role": "user", "content": str(case["query"])}],
        extra_headers=headers,
    )
    text = response_text(response)
    if not text:
        raise RuntimeError(f"{case['case_id']} returned no assistant text")
    if "Missing required x-client-demo-mode header" in text:
        raise RuntimeError(f"{case['case_id']} did not receive the trusted mode header")

    queried, returned, visible_text = source_metadata(text)
    return evaluation_item(
        {
            **case,
            "response": visible_text,
            "response_id": str(response.id),
            "source_evidence": f"Queried: {queried}; returned: {returned}",
            "applicable_dimensions_text": ", ".join(
                case.get("applicable_dimensions", [])
            ),
            "hard_gate_dimensions_text": ", ".join(
                case.get("hard_gate_dimensions", [])
            ),
        }
    )


def evaluation_item(item: dict[str, Any]) -> dict[str, Any]:
    result = {
        **item,
        "evaluation_query": (
            f"Mode: {item['mode']}\n"
            f"User query: {item['query']}\n"
            f"Expected behavior: {item['expected_behavior']}\n"
            "Applicable rubric dimensions: "
            f"{item['applicable_dimensions_text']}\n"
            "Mark every other rubric dimension inapplicable for this case."
        ),
        "evaluation_response": (
            f"{item['response']}\n\n"
            f"Trusted runtime source evidence: {item['source_evidence']}"
        ),
    }
    return result


def load_reused_invocations(
    path: Path,
    agent_version: str,
    cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    run_version = str(payload.get("run", {}).get("metadata", {}).get("azd_agent_version"))
    if run_version != agent_version:
        raise RuntimeError(
            f"Cached invocations are for agent version {run_version}, not {agent_version}"
        )
    invocations = payload.get("invocations")
    if not isinstance(invocations, list) or not invocations:
        raise RuntimeError("Cached evaluation file has no invocations")
    cached_by_id = {item["case_id"]: item for item in invocations}
    missing = [case["case_id"] for case in cases if case["case_id"] not in cached_by_id]
    if missing:
        raise RuntimeError(f"Cached evaluation is missing cases: {', '.join(missing)}")
    items = []
    for case in cases:
        item = {
            **cached_by_id[case["case_id"]],
            **case,
            "applicable_dimensions_text": ", ".join(
                case.get("applicable_dimensions", [])
            ),
            "hard_gate_dimensions_text": ", ".join(
                case.get("hard_gate_dimensions", [])
            ),
        }
        items.append(evaluation_item(item))
    return items


def get_or_create_rubric(
    project: AIProjectClient,
    *,
    rubric: dict[str, Any],
) -> tuple[str, str, bool]:
    name = str(rubric["name"])
    existing = [
        evaluator
        for evaluator in project.beta.evaluators.list(type="custom")
        if getattr(evaluator, "name", None) == name
    ]
    if existing:
        selected = max(existing, key=lambda item: str(getattr(item, "version", "")))
        selected_metadata = getattr(selected, "metadata", None) or {}
        if (
            isinstance(selected.definition, RubricBasedEvaluatorDefinition)
            and selected_metadata.get("local_rubric_version") == rubric["version"]
        ):
            return name, str(selected.version), False

    max_weight = max(float(dimension["weight"]) for dimension in rubric["dimensions"])
    dimensions = []
    for dimension in rubric["dimensions"]:
        raw_weight = float(dimension["weight"])
        weight = (
            round(raw_weight / max_weight * 10)
            if raw_weight <= 1
            else round(raw_weight)
        )
        description = str(dimension.get("description") or "").strip()
        if not description:
            description = ". ".join(dimension.get("criteria", []))
        if dimension.get("hard_gate"):
            description = description.rstrip(".") + (
                ". This is a hard gate when applicable; any violation requires "
                "the lowest dimension score."
            )
        dimensions.append(
            {
                "id": dimension["id"],
                "description": description,
                "weight": max(1, min(10, weight)),
                "always_applicable": bool(dimension.get("always_applicable", False)),
            }
        )

    scoring = rubric.get("scoring") or {}
    hard_gate_thresholds = {
        str(dimension["id"]): float(dimension.get("threshold", 1.0))
        for dimension in rubric["dimensions"]
        if dimension.get("hard_gate")
    }
    created = project.beta.evaluators.create_version(
        name=name,
        evaluator_version={
            "name": name,
            "categories": [EvaluatorCategory.QUALITY],
            "display_name": rubric.get("display_name", "Bank servicing rubric"),
            "description": rubric.get(
                "description",
                "Retail bank servicing quality and compliance rubric.",
            ),
            "metadata": {
                "local_rubric_version": rubric["version"],
                "rubric_api": "native",
                "jurisdiction": rubric.get("jurisdiction", ""),
                "hard_gate_thresholds": json.dumps(
                    hard_gate_thresholds,
                    sort_keys=True,
                ),
            },
            "definition": {
                "type": EvaluatorDefinitionType.RUBRIC,
                "dimensions": dimensions,
                "pass_threshold": float(scoring.get("pass_threshold", 0.9)),
            },
        },
    )
    if not isinstance(created.definition, RubricBasedEvaluatorDefinition):
        raise RuntimeError("Foundry did not create a native rubric evaluator")
    return name, str(created.version), True


def testing_criteria(
    *,
    model: str,
    rubric_name: str,
    rubric_version: str,
) -> list[TestingCriterionAzureAIEvaluator]:
    return [
        TestingCriterionAzureAIEvaluator(
            type="azure_ai_evaluator",
            name=rubric_name,
            evaluator_name=rubric_name,
            evaluator_version=rubric_version,
            initialization_parameters={
                "deployment_name": model,
            },
            data_mapping={
                "query": "{{item.evaluation_query}}",
                "response": "{{item.evaluation_response}}",
            },
        )
    ]


def metadata_started(
    path: Path,
    *,
    eval_id: str,
    run_id: str,
    run_name: str,
    agent_version: str,
    started_at: str,
) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    environment = data["environments"][data["defaultEnvironment"]]
    environment["lastEval"] = {
        "evalId": eval_id,
        "evalRunId": run_id,
        "runName": run_name,
        "suiteName": f"presenter-v{agent_version}-header-aware",
        "suiteVersion": "2.0.0",
        "agentVersion": agent_version,
        "startedAt": started_at,
        "status": "running",
    }
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def metadata_completed(
    path: Path,
    *,
    result_file: Path,
    summary_file: Path,
    status: str,
    completed_at: str,
    counts: dict[str, int],
    report_url: str,
    hard_gates: dict[str, Any],
) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    environment = data["environments"][data["defaultEnvironment"]]
    last_eval = environment["lastEval"]
    last_eval.update(
        {
            "completedAt": completed_at,
            "status": status,
            "passed": counts.get("passed", 0),
            "failed": counts.get("failed", 0),
            "errored": counts.get("errored", 0),
            "resultFile": str(result_file),
            "summaryFile": str(summary_file),
            "reportUrl": report_url,
            "hardGatePassed": bool(hard_gates["passed"]),
            "hardGateFailureCount": int(hard_gates["failureCount"]),
        }
    )
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def result_counts(run: Any) -> dict[str, int]:
    counts = getattr(run, "result_counts", None)
    if counts is None:
        return {}
    payload = counts.model_dump() if hasattr(counts, "model_dump") else dict(counts)
    return {key: int(value) for key, value in payload.items() if isinstance(value, int)}


def metric_summary(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for item in items:
        for result in item.get("results", []):
            name = result.get("name") or result.get("metric")
            if not name:
                continue
            entry = summary.setdefault(
                str(name),
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


def dimension_summary(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for item in items:
        for result in item.get("results", []):
            if result.get("name") != "bank_servicing_rubric":
                continue
            properties = result.get("properties") or {}
            for dimension in properties.get("dimension_scores", []):
                name = dimension.get("id")
                if not name:
                    continue
                entry = summary.setdefault(
                    str(name),
                    {"scores": [], "applicable": 0, "skipped": 0},
                )
                if dimension.get("applicable") is False:
                    entry["skipped"] += 1
                    continue
                score = dimension.get("score")
                if isinstance(score, (int, float)):
                    entry["scores"].append(float(score))
                    entry["applicable"] += 1
    for entry in summary.values():
        scores = entry.pop("scores")
        entry["meanScore"] = sum(scores) / len(scores) if scores else None
    return summary


def hard_gate_summary(
    items: list[dict[str, Any]],
    rubric: dict[str, Any],
) -> dict[str, Any]:
    thresholds = {
        str(dimension["id"]): float(dimension.get("threshold", 1.0))
        for dimension in rubric["dimensions"]
        if dimension.get("hard_gate")
    }
    evaluated = 0
    failures: list[dict[str, Any]] = []
    for item in items:
        datasource_item = item.get("datasource_item") or {}
        item_id = str(datasource_item.get("case_id") or item.get("id") or "")
        required_gates = {
            str(dimension_id)
            for dimension_id in datasource_item.get("hard_gate_dimensions", [])
        }
        rubric_result = next(
            (
                result
                for result in item.get("results", [])
                if result.get("name") == "bank_servicing_rubric"
            ),
            None,
        )
        scored_dimensions = {}
        if rubric_result is not None:
            properties = rubric_result.get("properties") or {}
            scored_dimensions = {
                str(dimension.get("id") or ""): dimension
                for dimension in properties.get("dimension_scores", [])
            }

        for dimension_id in sorted(required_gates):
            evaluated += 1
            threshold = thresholds.get(dimension_id)
            dimension = scored_dimensions.get(dimension_id)
            score = dimension.get("score") if dimension else None
            normalized_score = (
                max(0.0, min(1.0, (float(score) - 1.0) / 4.0))
                if isinstance(score, (int, float))
                else None
            )
            failure_reason = None
            if threshold is None:
                failure_reason = "hard gate is not defined in the rubric"
            elif dimension is None:
                failure_reason = "dimension score is missing"
            elif dimension.get("applicable") is False:
                failure_reason = "required hard gate was marked inapplicable"
            elif normalized_score is None:
                failure_reason = "dimension score is invalid"
            elif normalized_score < threshold:
                failure_reason = "dimension score is below the hard-gate threshold"

            if failure_reason:
                failures.append(
                    {
                        "itemId": item_id,
                        "dimension": dimension_id,
                        "score": score,
                        "normalizedScore": normalized_score,
                        "threshold": threshold,
                        "reason": failure_reason,
                    }
                )
    return {
        "passed": not failures,
        "evaluated": evaluated,
        "failureCount": len(failures),
        "failures": failures,
    }


def write_summary(
    path: Path,
    *,
    agent_version: str,
    eval_id: str,
    run_id: str,
    status: str,
    counts: dict[str, int],
    metrics: dict[str, dict[str, Any]],
    dimensions: dict[str, dict[str, Any]],
    hard_gates: dict[str, Any],
    report_url: str,
    case_count: int,
    rubric_version: str,
) -> None:
    rows_list: list[str] = []
    for name, values in sorted(metrics.items()):
        mean = values["meanScore"]
        mean_text = "n/a" if mean is None else f"{mean:.3f}"
        rows_list.append(
            f"| {name} | {mean_text} | {values['passed']} | "
            f"{values['failed']} | {values['errored']} |"
        )
    rows = "\n".join(rows_list)
    dimension_rows_list: list[str] = []
    for name, values in sorted(dimensions.items()):
        mean = values["meanScore"]
        mean_text = "n/a" if mean is None else f"{mean:.2f}"
        dimension_rows_list.append(
            f"| {name} | {mean_text} | {values['applicable']} | "
            f"{values['skipped']} |"
        )
    dimension_rows = "\n".join(dimension_rows_list)
    text = f"""# Foundry presenter evaluation

- Agent: `bank-servicing-agent` version `{agent_version}`
- Invocation: precomputed responses with trusted `x-client-demo-mode`
- Cases: {case_count} synthetic, read-only cases
- Eval ID: `{eval_id}`
- Run ID: `{run_id}`
- Status: `{status}`
- Result counts: {json.dumps(counts, sort_keys=True)}
- Native rubric: `bank_servicing_rubric` version `{rubric_version}` (preview)
- Local hard-gate result: `{"passed" if hard_gates["passed"] else "failed"}` ({hard_gates["failureCount"]} failures)
- Report: {report_url}

| Evaluator | Mean score | Passed | Failed | Errored |
| --- | ---: | ---: | ---: | ---: |
{rows}

## Rubric dimensions

| Dimension | Mean (1-5) | Applicable cases | Skipped cases |
| --- | ---: | ---: | ---: |
{dimension_rows}

The standard Foundry agent-target runner cannot forward custom client headers.
This run therefore invoked the production agent first with the required trusted
mode header, then used Foundry's supported JSONL dataset-evaluation path to score
the resulting query/response pairs. No Work IQ response content was persisted in
this evaluation dataset.
"""
    path.write_text(text, encoding="utf-8")


def main() -> None:
    args = parse_args()
    rubric = json.loads(args.rubric.read_text(encoding="utf-8"))
    cases = load_cases(args.dataset)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    with AzureCliCredential() as credential:
        if args.reuse_invocations:
            items = load_reused_invocations(
                args.reuse_invocations,
                args.agent_version,
                cases,
            )
        else:
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
                items = [
                    invoke_case(
                        agent_client,
                        case=case,
                        model=args.model,
                        version=args.agent_version,
                    )
                    for case in cases
                ]
            finally:
                agent_client.close()

        with AIProjectClient(
            endpoint=args.project_endpoint,
            credential=credential,
        ) as project:
            rubric_name, rubric_version, rubric_created = get_or_create_rubric(
                project,
                rubric=rubric,
            )
            with project.get_openai_client() as client:
                evaluation = client.evals.create(
                    name=f"bank-servicing-v{args.agent_version}-header-aware",
                    metadata={
                        "azd_agent": args.agent_name,
                        "azd_agent_version": args.agent_version,
                        "invocation_mode": "precomputed_header_aware",
                    },
                    data_source_config=DataSourceConfigCustom(
                        type="custom",
                        item_schema={
                            "type": "object",
                            "properties": {
                                "evaluation_query": {"type": "string"},
                                "evaluation_response": {"type": "string"},
                            },
                            "required": [
                                "evaluation_query",
                                "evaluation_response",
                            ],
                        },
                        include_sample_schema=True,
                    ),
                    testing_criteria=testing_criteria(
                        model=args.model,
                        rubric_name=rubric_name,
                        rubric_version=rubric_version,
                    ),
                )
                run_name = f"bank-servicing-v{args.agent_version}-presenter-{timestamp}"
                run = client.evals.runs.create(
                    eval_id=evaluation.id,
                    name=run_name,
                    metadata={
                        "azd_agent": args.agent_name,
                        "azd_agent_version": args.agent_version,
                        "trigger_type": "presenter_evidence",
                    },
                    data_source=CreateEvalJSONLRunDataSourceParam(
                        type="jsonl",
                        source=SourceFileContent(
                            type="file_content",
                            content=[
                                SourceFileContentContent(item=item) for item in items
                            ],
                        ),
                    ),
                )
                started_at = datetime.now(UTC).isoformat()
                metadata_started(
                    args.metadata,
                    eval_id=evaluation.id,
                    run_id=run.id,
                    run_name=run_name,
                    agent_version=args.agent_version,
                    started_at=started_at,
                )

                while run.status not in TERMINAL_STATES:
                    time.sleep(5)
                    run = client.evals.runs.retrieve(
                        run_id=run.id,
                        eval_id=evaluation.id,
                    )

                output_items = [
                    item.model_dump()
                    for item in client.evals.runs.output_items.list(
                        run_id=run.id,
                        eval_id=evaluation.id,
                    )
                ]
                evaluation_payload = client.evals.retrieve(evaluation.id).model_dump()

    result_dir = args.results_root / evaluation.id
    result_dir.mkdir(parents=True, exist_ok=True)
    result_file = result_dir / f"{run.id}.json"
    summary_file = result_dir / "summary.md"
    counts = result_counts(run)
    metrics = metric_summary(output_items)
    dimensions = dimension_summary(output_items)
    hard_gates = hard_gate_summary(output_items, rubric)
    payload = {
        "evaluation": evaluation_payload,
        "run": run.model_dump(),
        "invocations": items,
        "output_items": output_items,
        "rubric": {
            "name": rubric_name,
            "version": rubric_version,
            "created": rubric_created,
            "preview": True,
        },
        "hardGateResult": hard_gates,
    }
    result_file.write_text(
        json.dumps(payload, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    report_url = str(getattr(run, "report_url", "") or "")
    completed_at = datetime.now(UTC).isoformat()
    write_summary(
        summary_file,
        agent_version=args.agent_version,
        eval_id=evaluation.id,
        run_id=run.id,
        status=str(run.status),
        counts=counts,
        metrics=metrics,
        dimensions=dimensions,
        hard_gates=hard_gates,
        report_url=report_url,
        case_count=len(cases),
        rubric_version=rubric_version,
    )
    metadata_completed(
        args.metadata,
        result_file=result_file.relative_to(args.metadata.parent),
        summary_file=summary_file.relative_to(args.metadata.parent),
        status=str(run.status),
        completed_at=completed_at,
        counts=counts,
        report_url=report_url,
        hard_gates=hard_gates,
    )
    print(
        json.dumps(
            {
                "evalId": evaluation.id,
                "runId": run.id,
                "status": run.status,
                "counts": counts,
                "metrics": metrics,
                "hardGateResult": hard_gates,
                "reportUrl": report_url,
                "resultFile": str(result_file),
                "summaryFile": str(summary_file),
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
