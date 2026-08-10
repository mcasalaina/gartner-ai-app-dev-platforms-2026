#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


BACKUP_DIR = ".legacy-viewer-schema"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def case_dimensions(row: dict[str, Any]) -> dict[str, Any]:
    dimensions = dict(row.get("dimensions") or {})
    behavior = row.get("behavior")
    if isinstance(behavior, str) and behavior:
        dimensions["behavior"] = behavior
    return dimensions


def migrate_scores(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    migrated = []
    for source in rows:
        row = dict(source)
        row["dimensions"] = case_dimensions(row)

        verdict = dict(row.get("verdict") or {})
        judge_dimensions = dict(verdict.get("dimensions") or {})
        verdict["dimension_applicability"] = {
            name: value is not None for name, value in judge_dimensions.items()
        }
        row["verdict"] = verdict
        row["score_keys"] = list(judge_dimensions)
        row["not_applicable_score_keys"] = [
            name for name, value in judge_dimensions.items() if value is None
        ]
        migrated.append(row)
    return migrated


def migrate_transcripts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    migrated = []
    for source in rows:
        row = dict(source)
        row["dimensions"] = case_dimensions(row)
        migrated.append(row)
    return migrated


def build_test_set(transcripts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    test_set = []
    for transcript in transcripts:
        dimensions = case_dimensions(transcript)
        behavior = str(transcript.get("behavior") or "")
        test_set.append(
            {
                "type": transcript.get("type", "prompt"),
                "test_case_id": transcript["test_case_id"],
                "dimensions": dimensions,
                "seed": {
                    "title": behavior.replace("_", " ").title(),
                    "description": dimensions.get("expected_behavior", ""),
                },
            }
        )
    return test_set


def build_taxonomy(scores: list[dict[str, Any]]) -> dict[str, Any]:
    behaviors: dict[str, str] = {}
    for row in scores:
        behavior = str(row.get("behavior") or "")
        expected = str((row.get("dimensions") or {}).get("expected_behavior") or "")
        if behavior and behavior not in behaviors:
            behaviors[behavior] = expected
    return {
        "behavior": {
            "name": "Bank servicing safety and quality",
            "definition": (
                "Evaluates source routing, banking boundaries, identity confirmation, "
                "privacy, injection resistance, continuity, and response quality."
            ),
        },
        "behavior_categories": [
            {
                "name": name,
                "definition": definition,
                "examples": [],
                "permissible": True,
            }
            for name, definition in behaviors.items()
        ],
    }


def ensure_backup(run_dir: Path, files: list[Path]) -> Path:
    backup = run_dir / BACKUP_DIR
    backup.mkdir(exist_ok=True)
    for path in files:
        destination = backup / path.name
        if not destination.exists():
            shutil.copy2(path, destination)
    return backup


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate a legacy ASSERT run to the current viewer artifact schema"
    )
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()

    run_dir = args.run_dir.resolve()
    suite_dir = run_dir.parent
    scores_path = run_dir / "scores.jsonl"
    transcripts_path = run_dir / "inference_set.jsonl"
    manifest_path = run_dir / "manifest.json"
    for required in (scores_path, transcripts_path, manifest_path):
        if not required.is_file():
            raise FileNotFoundError(f"Missing ASSERT artifact: {required}")

    scores = read_jsonl(scores_path)
    transcripts = read_jsonl(transcripts_path)
    if not scores or not transcripts:
        raise ValueError("The ASSERT run must contain scores and transcripts")

    backup = ensure_backup(run_dir, [scores_path, transcripts_path])
    migrated_scores = migrate_scores(scores)
    migrated_transcripts = migrate_transcripts(transcripts)
    write_jsonl(scores_path, migrated_scores)
    write_jsonl(transcripts_path, migrated_transcripts)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    created_at = manifest.get("started_at") or datetime.now(UTC).isoformat()
    write_json(suite_dir / "suite.json", {"created_at": created_at})
    write_json(suite_dir / "taxonomy.json", build_taxonomy(migrated_scores))
    write_jsonl(suite_dir / "test_set.jsonl", build_test_set(migrated_transcripts))
    viewer_cache = run_dir / ".viewer"
    if viewer_cache.is_dir():
        shutil.rmtree(viewer_cache)
    write_json(
        run_dir / "viewer-schema-migration.json",
        {
            "schema": "current-assert-viewer",
            "migrated_at": datetime.now(UTC).isoformat(),
            "originals": [
                str((backup / scores_path.name).relative_to(run_dir)),
                str((backup / transcripts_path.name).relative_to(run_dir)),
            ],
        },
    )

    print(run_dir)


if __name__ == "__main__":
    main()
