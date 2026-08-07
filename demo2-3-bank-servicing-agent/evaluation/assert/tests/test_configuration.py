from __future__ import annotations

import json
from pathlib import Path

import yaml

from bank_assert.config_validation import REQUIRED_COVERAGE_TAGS, validate_repository

ROOT = Path(__file__).resolve().parents[3]


def test_repository_assert_configuration_is_consistent() -> None:
    assert validate_repository(ROOT) == []


def test_reviewed_suite_mixes_natural_prompts_and_multiturn_scenarios() -> None:
    seed_path = (
        ROOT / "evaluation" / "assert" / "config" / "seeds" / "bank-servicing-conversations.jsonl"
    )
    rows = [json.loads(line) for line in seed_path.read_text().splitlines() if line]
    assert sum(row["type"] == "prompt" for row in rows) == 8
    assert sum(row["type"] == "scenario" for row in rows) == 4
    coverage_tags = {
        tag.strip()
        for row in rows
        for tag in str(row["dimensions"].get("coverage_tags", "")).split(",")
        if tag.strip()
    }
    assert coverage_tags >= REQUIRED_COVERAGE_TAGS
    assert all(row["dimensions"]["expected_behavior"] for row in rows)
    assert all(
        row["dimensions"]["conversation_shape"] != "single_turn"
        for row in rows
        if row["type"] == "scenario"
    )


def test_reviewed_suite_configures_two_turn_tester_and_verified_source_lock() -> None:
    config_path = ROOT / "evaluation" / "assert" / "config" / "smoke.yaml"
    config = yaml.safe_load(config_path.read_text())
    inference = config["pipeline"]["inference"]
    lock = json.loads((ROOT / "evaluation" / "assert" / "assert-source.lock.json").read_text())
    assert config["suite"] == "bank-servicing-conversations"
    assert inference["max_turns"] == 2
    assert inference["tester"]["model"]["name"] == "azure/gpt-5.4-mini"
    assert lock["verification"]["status"] == "verified"
