from __future__ import annotations

import json
from pathlib import Path

from scripts.run_presenter_evaluation import (
    hard_gate_summary,
    load_reused_invocations,
)
from scripts.run_classic_comprehensive_evaluation import (
    agent_outcome_criteria,
    intent_resolution_criteria,
    load_cases,
    response_quality_criteria,
    tool_quality_criteria,
    unified_standard_criteria,
)


def test_reused_invocations_refresh_rubric_dimensions(tmp_path) -> None:
    cache = tmp_path / "cached.json"
    cache.write_text(
        json.dumps(
            {
                "run": {"metadata": {"azd_agent_version": "15"}},
                "invocations": [
                    {
                        "case_id": "case-1",
                        "mode": "customer_servicing",
                        "query": "Help me.",
                        "expected_behavior": "Use the old rubric.",
                        "response": "Response",
                        "source_evidence": "Queried: none; returned: none",
                        "applicable_dimensions_text": "old_dimension",
                        "hard_gate_dimensions_text": "old_dimension",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    cases = [
        {
            "case_id": "case-1",
            "mode": "customer_servicing",
            "query": "Help me.",
            "expected_behavior": "Use the current rubric.",
            "applicable_dimensions": ["current_dimension"],
            "hard_gate_dimensions": ["current_dimension"],
        }
    ]

    item = load_reused_invocations(cache, "15", cases)[0]

    assert item["applicable_dimensions_text"] == "current_dimension"
    assert item["hard_gate_dimensions_text"] == "current_dimension"
    assert "current_dimension" in item["evaluation_query"]
    assert "old_dimension" not in item["evaluation_query"]


def test_hard_gates_are_scoped_to_each_case() -> None:
    rubric = {
        "dimensions": [
            {"id": "required_gate", "hard_gate": True, "threshold": 1.0},
            {"id": "unrelated_gate", "hard_gate": True, "threshold": 1.0},
        ]
    }
    items = [
        {
            "id": "1",
            "datasource_item": {
                "case_id": "case-1",
                "hard_gate_dimensions": ["required_gate"],
            },
            "results": [
                {
                    "name": "bank_servicing_rubric",
                    "properties": {
                        "dimension_scores": [
                            {
                                "id": "required_gate",
                                "score": 5,
                                "applicable": True,
                            },
                            {
                                "id": "unrelated_gate",
                                "score": 1,
                                "applicable": True,
                            },
                        ]
                    },
                }
            ],
        }
    ]

    summary = hard_gate_summary(items, rubric)

    assert summary["passed"] is True
    assert summary["evaluated"] == 1
    assert summary["failures"] == []


def test_missing_required_hard_gate_fails_closed() -> None:
    rubric = {
        "dimensions": [
            {"id": "required_gate", "hard_gate": True, "threshold": 1.0}
        ]
    }
    items = [
        {
            "id": "1",
            "datasource_item": {
                "case_id": "case-1",
                "hard_gate_dimensions": ["required_gate"],
            },
            "results": [
                {
                    "name": "bank_servicing_rubric",
                    "properties": {"dimension_scores": []},
                }
            ],
        }
    ]

    summary = hard_gate_summary(items, rubric)

    assert summary["passed"] is False
    assert summary["evaluated"] == 1
    assert summary["failures"][0]["itemId"] == "case-1"
    assert summary["failures"][0]["reason"] == "dimension score is missing"


def test_classic_dataset_has_twenty_realistic_inputs() -> None:
    dataset = (
        Path(__file__).resolve().parents[3]
        / "evaluation/foundry/datasets/classic_comprehensive_cases.jsonl"
    )

    cases = load_cases(dataset)

    assert len(cases) == 20
    for case in cases:
        query = case["query"].lower()
        assert "synthetic" not in query
        assert "demo" not in query


def test_classic_criteria_cover_requested_evaluators() -> None:
    criteria = unified_standard_criteria("gpt-5.4-mini")

    assert {criterion["evaluator_name"] for criterion in criteria} == {
        "builtin.groundedness",
        "builtin.relevance",
        "builtin.fluency",
        "builtin.task_completion",
        "builtin.task_adherence",
        "builtin.intent_resolution",
        "builtin.tool_call_accuracy",
        "builtin.tool_selection",
        "builtin.tool_input_accuracy",
        "builtin.tool_output_utilization",
        "builtin.tool_call_success",
    }
