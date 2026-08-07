from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import RubricBasedEvaluatorDefinition
from azure.identity import AzureCliCredential

from run_presenter_evaluation import get_or_create_rubric


PROHIBITED_RUBRIC_TERMS = ("synthetic",)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-endpoint", required=True)
    parser.add_argument("--rubric", type=Path, required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--delete-prior-versions", action="store_true")
    return parser.parse_args()


def load_rubric(path: Path) -> dict[str, Any]:
    rubric = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rubric, dict):
        raise ValueError("Rubric file must contain a JSON object")
    return rubric


def assert_clean_definition(
    payload: dict[str, Any],
    expected_ids: set[str],
    expected_hard_gate_ids: set[str],
) -> None:
    serialized = json.dumps(payload, sort_keys=True).casefold()
    prohibited = [term for term in PROHIBITED_RUBRIC_TERMS if term in serialized]
    if prohibited:
        raise RuntimeError(
            "Registered rubric contains prohibited terms: " + ", ".join(prohibited)
        )
    definition = payload.get("definition") or {}
    dimensions = definition.get("dimensions") or []
    actual_ids = {
        str(dimension.get("id"))
        for dimension in dimensions
        if isinstance(dimension, dict) and dimension.get("id")
    }
    if actual_ids != expected_ids:
        raise RuntimeError(
            f"Registered dimension mismatch: expected {sorted(expected_ids)}, "
            f"found {sorted(actual_ids)}"
        )
    if definition.get("type") != "rubric":
        raise RuntimeError("Registered evaluator is not a native rubric")
    metadata = payload.get("metadata") or {}
    registered_hard_gates = json.loads(metadata.get("hard_gate_thresholds", "{}"))
    if set(registered_hard_gates) != expected_hard_gate_ids:
        raise RuntimeError(
            "Registered hard-gate metadata mismatch: "
            f"expected {sorted(expected_hard_gate_ids)}, "
            f"found {sorted(registered_hard_gates)}"
        )


def main() -> None:
    args = parse_args()
    rubric = load_rubric(args.rubric)
    expected_ids = {
        str(dimension["id"])
        for dimension in rubric.get("dimensions", [])
        if isinstance(dimension, dict) and dimension.get("id")
    }
    expected_hard_gate_ids = {
        str(dimension["id"])
        for dimension in rubric.get("dimensions", [])
        if isinstance(dimension, dict) and dimension.get("hard_gate")
    }
    credential = AzureCliCredential()
    try:
        with AIProjectClient(
            endpoint=args.project_endpoint,
            credential=credential,
        ) as project:
            name, version, created = get_or_create_rubric(project, rubric=rubric)
            if version != args.expected_version:
                raise RuntimeError(
                    f"Expected Foundry evaluator version {args.expected_version}, "
                    f"but resolved version {version}"
                )
            registered = project.beta.evaluators.get_version(name=name, version=version)
            if not isinstance(registered.definition, RubricBasedEvaluatorDefinition):
                raise RuntimeError("Foundry did not return a native rubric evaluator")
            payload = registered.as_dict()
            assert_clean_definition(
                payload,
                expected_ids,
                expected_hard_gate_ids,
            )

            deleted_versions: list[str] = []
            if args.delete_prior_versions:
                prior_versions = [
                    str(item.version)
                    for item in project.beta.evaluators.list_versions(name=name)
                    if str(item.version) != version
                ]
                for prior_version in prior_versions:
                    project.beta.evaluators.delete_version(
                        name=name,
                        version=prior_version,
                    )
                    deleted_versions.append(prior_version)

            remaining_versions = [
                str(item.version)
                for item in project.beta.evaluators.list_versions(name=name)
            ]
    finally:
        credential.close()

    print(
        json.dumps(
            {
                "name": name,
                "version": version,
                "localRubricVersion": rubric["version"],
                "created": created,
                "displayName": payload.get("display_name"),
                "jurisdiction": (payload.get("metadata") or {}).get("jurisdiction"),
                "dimensionCount": len(expected_ids),
                "prohibitedTerms": [],
                "deletedVersions": deleted_versions,
                "remainingVersions": remaining_versions,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
