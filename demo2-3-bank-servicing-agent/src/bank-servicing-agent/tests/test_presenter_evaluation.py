from __future__ import annotations

import json

from scripts.run_presenter_evaluation import (
    hard_gate_summary,
    load_reused_invocations,
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
