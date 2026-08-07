from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

PROJECT_ENDPOINT = "https://4iq-foundry-project-resource.services.ai.azure.com/api/projects/4iq-foundry-project"
TOOLBOX_NAME = "bank-servicing-agent-tools"
WORKIQ_CONNECTION = "WorkIQ"
FABRIC_CONNECTION = "fabric-iq-acmebank"
BANK_POLICY_CONNECTION = "kb-acme-bank-foundryiq"
SERVICE_CORPUS_CONNECTION = "svc-demo1-bank-services-foundryiq"
DEMO1_PDF = "demo1-deep-research-agent/examples/generated-bank-strategy/bank-strategy-report.pdf"

REVIEW_STATES = ("draft", "qc_failed", "pending_review", "approved", "rejected", "published")
ALLOWED_TRANSITIONS = {
    "draft": {"qc_failed", "pending_review"},
    "qc_failed": {"draft", "pending_review"},
    "pending_review": {"approved", "rejected"},
    "rejected": {"draft"},
    "approved": {"published"},
    "published": set(),
}


class ContractValidationError(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def compute_service_content_hash(service_version: dict[str, Any]) -> str:
    payload = copy.deepcopy(service_version)
    payload.pop("content_hash", None)
    return "sha256:" + hashlib.sha256(canonical_bytes(payload)).hexdigest()


def compute_manifest_etag(manifest: dict[str, Any]) -> str:
    payload = copy.deepcopy(manifest)
    payload.pop("etag", None)
    digest = hashlib.sha256(canonical_bytes(payload)).hexdigest()[:24]
    return f'W/"rv-{manifest["record_version"]}-{digest}"'


def _ensure(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def _artifact_index(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {artifact["artifact_id"]: artifact for artifact in manifest.get("source_artifacts", [])}


def _citation_ids(manifest: dict[str, Any]) -> set[str]:
    return {citation["citation_id"] for citation in manifest.get("citations", [])}


def _service_version_ids(manifest: dict[str, Any]) -> set[str]:
    return {version["version_id"] for version in manifest.get("service_description_versions", [])}


def validate_manifest(manifest: dict[str, Any], repo_root: str | Path | None = None) -> list[str]:
    errors: list[str] = []
    _ensure(manifest.get("schema_version") == "1.0.0", "schema_version must be 1.0.0", errors)
    _ensure(
        manifest.get("source_contract", {}).get("source_document_path") == DEMO1_PDF,
        "source_contract.source_document_path must point at the Demo 1 PDF",
        errors,
    )
    _ensure(
        manifest.get("source_contract", {}).get("project_endpoint") == PROJECT_ENDPOINT,
        "source_contract.project_endpoint must match the verified Foundry project endpoint",
        errors,
    )
    _ensure(
        BANK_POLICY_CONNECTION in manifest.get("source_contract", {}).get("forbidden_publish_connections", []),
        "forbidden publish connections must include the bank policy knowledge base",
        errors,
    )
    review = manifest.get("review", {})
    state = review.get("state")
    _ensure(state in REVIEW_STATES, f"review.state must be one of {REVIEW_STATES}", errors)
    _ensure(
        manifest.get("publication", {}).get("foundry_iq_connection_name") != BANK_POLICY_CONNECTION,
        "publication.foundry_iq_connection_name must not point at the bank policy knowledge base",
        errors,
    )
    _ensure(manifest.get("etag") == compute_manifest_etag(manifest), "etag does not match canonical manifest contents", errors)
    artifacts = _artifact_index(manifest)
    citations = _citation_ids(manifest)
    service_versions = _service_version_ids(manifest)
    _ensure("src-pdf-bank-strategy" in artifacts, "source_artifacts must include src-pdf-bank-strategy", errors)

    for artifact in manifest.get("source_artifacts", []):
        _ensure("relative_path" in artifact, f"source artifact {artifact.get('artifact_id')} must include relative_path", errors)
        if repo_root is not None:
            asset_path = Path(repo_root) / artifact["relative_path"]
            _ensure(asset_path.exists(), f"source artifact path does not exist: {artifact['relative_path']}", errors)

    for citation in manifest.get("citations", []):
        _ensure(citation.get("artifact_id") in artifacts, f"citation {citation.get('citation_id')} references unknown artifact", errors)

    for chunk in manifest.get("extracted_text", []):
        _ensure(chunk.get("artifact_id") in artifacts, f"extracted_text {chunk.get('chunk_id')} references unknown artifact", errors)
        for citation_id in chunk.get("citations", []):
            _ensure(citation_id in citations, f"extracted_text {chunk.get('chunk_id')} references unknown citation {citation_id}", errors)

    for image in manifest.get("image_metadata", []):
        _ensure(image.get("artifact_id") in artifacts, f"image_metadata {image.get('image_id')} references unknown artifact", errors)
        for citation_id in image.get("citations", []):
            _ensure(citation_id in citations, f"image_metadata {image.get('image_id')} references unknown citation {citation_id}", errors)

    feedback_ids = {feedback["feedback_id"] for feedback in manifest.get("feedback_lineage", [])}
    for media in manifest.get("generated_flux_media", []):
        _ensure(media.get("derived_from_version_id") in service_versions, f"generated_flux_media {media.get('media_id')} references unknown service version", errors)
        for citation_id in media.get("citations", []):
            _ensure(citation_id in citations, f"generated_flux_media {media.get('media_id')} references unknown citation {citation_id}", errors)

    for feedback in manifest.get("feedback_lineage", []):
        _ensure(feedback.get("source_version_id") in service_versions, f"feedback {feedback.get('feedback_id')} references unknown source version", errors)
        _ensure(feedback.get("derived_version_id") in service_versions, f"feedback {feedback.get('feedback_id')} references unknown derived version", errors)

    for draft in manifest.get("synthetic_account_opening_drafts", []):
        _ensure(draft.get("service_version_id") in service_versions, f"account opening draft {draft.get('draft_id')} references unknown service version", errors)
        for citation_id in draft.get("citations", []):
            _ensure(citation_id in citations, f"account opening draft {draft.get('draft_id')} references unknown citation {citation_id}", errors)

    sequences: list[int] = []
    for version in manifest.get("service_description_versions", []):
        sequences.append(version.get("sequence"))
        _ensure(version.get("immutable") is True, f"service version {version.get('version_id')} must be immutable", errors)
        _ensure(version.get("content_hash") == compute_service_content_hash(version), f"service version {version.get('version_id')} has an invalid content_hash", errors)
        for citation_id in version.get("citations", []):
            _ensure(citation_id in citations, f"service version {version.get('version_id')} references unknown citation {citation_id}", errors)
        for feedback_id in version.get("derived_from_feedback", []):
            _ensure(feedback_id in feedback_ids, f"service version {version.get('version_id')} references unknown feedback {feedback_id}", errors)
    _ensure(sequences == sorted(sequences), "service_description_versions.sequence values must be sorted ascending", errors)

    history = review.get("history", [])
    _ensure(bool(history), "review.history must not be empty", errors)
    if history:
        _ensure(history[0].get("to_state") == "draft", "review.history must start in draft", errors)
        previous_state = history[0].get("to_state")
        for entry in history[1:]:
            next_state = entry.get("to_state")
            _ensure(
                next_state in ALLOWED_TRANSITIONS.get(previous_state, set()),
                f"review.history contains invalid transition: {previous_state} -> {next_state}",
                errors,
            )
            previous_state = next_state
        _ensure(history[-1].get("to_state") == state, "review.history must end at the current state", errors)
    return errors


def assert_valid_manifest(manifest: dict[str, Any], repo_root: str | Path | None = None) -> None:
    errors = validate_manifest(manifest, repo_root=repo_root)
    if errors:
        raise ContractValidationError("\n".join(errors))


def validate_transition(current_state: str, next_state: str) -> None:
    if next_state not in ALLOWED_TRANSITIONS.get(current_state, set()):
        raise ContractValidationError(f"invalid lifecycle transition: {current_state} -> {next_state}")


def transition_manifest(
    manifest: dict[str, Any],
    next_state: str,
    *,
    if_match: str | None = None,
    expected_record_version: int | None = None,
    actor: str = "content.publisher",
    note: str = "",
    timestamp: str = "2026-08-04T14:30:00Z",
) -> dict[str, Any]:
    assert_valid_manifest(manifest)
    current_etag = compute_manifest_etag(manifest)
    if if_match is not None and if_match != current_etag:
        raise ContractValidationError(f"if-match mismatch: expected {current_etag}, received {if_match}")
    if expected_record_version is not None and expected_record_version != manifest.get("record_version"):
        raise ContractValidationError(
            f"record version mismatch: expected {manifest.get('record_version')}, received {expected_record_version}"
        )
    current_state = manifest["review"]["state"]
    validate_transition(current_state, next_state)
    updated = copy.deepcopy(manifest)
    updated["record_version"] += 1
    updated["review"]["state"] = next_state
    updated["review"]["updated_at"] = timestamp
    updated["review"]["updated_by"] = actor
    updated["review"]["history"].append(
        {
            "from_state": current_state,
            "to_state": next_state,
            "timestamp": timestamp,
            "actor": actor,
            "note": note or f"Transitioned from {current_state} to {next_state}.",
        }
    )
    if next_state == "pending_review":
        updated["review"]["qc_summary"]["status"] = "passed"
        for check_name in list(updated["review"]["qc_summary"]["checks"]):
            updated["review"]["qc_summary"]["checks"][check_name] = True
    elif next_state == "qc_failed":
        updated["review"]["qc_summary"]["status"] = "failed"
    elif next_state == "published":
        updated["publication"]["publish_state"] = "published"
        updated["publication"]["published_at"] = timestamp
    updated["etag"] = compute_manifest_etag(updated)
    assert_valid_manifest(updated)
    return updated


def build_publish_plan(
    manifest: dict[str, Any],
    *,
    source_manifest: str | Path,
    project_endpoint: str = PROJECT_ENDPOINT,
    foundry_iq_connection_name: str | None = None,
    blob_container: str | None = None,
    dry_run: bool = True,
    allow_remote_mutation: bool = False,
    apply: bool = False,
) -> dict[str, Any]:
    assert_valid_manifest(manifest)
    if manifest["review"]["state"] not in ("approved", "published"):
        raise ContractValidationError("publish planning requires review.state to be approved or published")
    connection_name = foundry_iq_connection_name or manifest["publication"]["foundry_iq_connection_name"]
    if connection_name == BANK_POLICY_CONNECTION:
        raise ContractValidationError(
            "refusing to plan against the existing bank policy knowledge base; use a separate Demo 1 corpus connection"
        )
    if project_endpoint != PROJECT_ENDPOINT:
        raise ContractValidationError("project endpoint does not match the verified Foundry project endpoint")
    container_name = blob_container or manifest["publication"]["blob_container"]
    latest_version = max(manifest["service_description_versions"], key=lambda item: item["sequence"])
    prefix = manifest["publication"]["blob_prefix"].rstrip("/")
    steps = [
        {
            "sequence": 10,
            "target": "blob",
            "action": "upload-manifest",
            "identity": "project_managed_identity",
            "payload": {
                "container": container_name,
                "blob_path": f"{prefix}/service-corpus.json",
                "content_type": "application/json",
            },
        },
        {
            "sequence": 20,
            "target": "blob",
            "action": "stage-source-document",
            "identity": "project_managed_identity",
            "payload": {
                "container": container_name,
                "blob_path": f"{prefix}/source/bank-strategy-report.pdf",
                "relative_path": manifest["source_contract"]["source_document_path"],
                "sha256": manifest["source_contract"]["source_document_sha256"],
            },
        },
        {
            "sequence": 30,
            "target": "foundry_iq",
            "action": "upsert-reviewed-service-corpus",
            "identity": "project_managed_identity",
            "payload": {
                "connection_name": connection_name,
                "corpus_id": manifest["corpus_id"],
                "version_id": latest_version["version_id"],
                "content_hash": latest_version["content_hash"],
                "if_match": manifest["etag"],
                "source_blob_path": f"{prefix}/service-corpus.json",
            },
        },
    ]
    plan = {
        "plan_version": "1.0.0",
        "dry_run": not (allow_remote_mutation and apply),
        "project_endpoint": project_endpoint,
        "source_manifest": str(source_manifest),
        "record_version": manifest["record_version"],
        "if_match": manifest["etag"],
        "steps": steps,
        "mutations_executed": False,
        "notes": [
            "Plan targets a separate Demo 1 service corpus connection and blob prefix.",
            "The bank policy knowledge base connection remains excluded from publish targets.",
        ],
    }
    if allow_remote_mutation and apply:
        plan["notes"].append(
            "Remote mutation authorization supplied; execution is intentionally disabled in this repository-safe workflow. Review the plan and run the az commands manually in a controlled deployment session."
        )
    return plan


def validate_toolbox_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    toolbox = manifest.get("toolbox", {})
    _ensure(manifest.get("schema_version") == "1.0.0", "toolbox schema_version must be 1.0.0", errors)
    _ensure(toolbox.get("name") == TOOLBOX_NAME, f"toolbox.name must be {TOOLBOX_NAME}", errors)
    _ensure(toolbox.get("project_endpoint") == PROJECT_ENDPOINT, "toolbox.project_endpoint must match the verified project endpoint", errors)
    tools = manifest.get("tools", [])
    indexed_tools = {tool.get("name"): tool for tool in tools if tool.get("name")}
    for required_name in ("customer_finance", "work_context", "bank_policy", "service_publication"):
        _ensure(required_name in indexed_tools, f"missing required tool {required_name}", errors)
    if "customer_finance" in indexed_tools:
        tool = indexed_tools["customer_finance"]
        _ensure(tool.get("type") == "fabric_iq_preview", "customer_finance must use fabric_iq_preview", errors)
        _ensure(tool.get("project_connection_id") == FABRIC_CONNECTION, f"customer_finance must use connection {FABRIC_CONNECTION}", errors)
        _ensure(tool.get("identity_mode") == "user_entra_token", "customer_finance must preserve user identity", errors)
    if "work_context" in indexed_tools:
        tool = indexed_tools["work_context"]
        _ensure(tool.get("type") == "mcp", "work_context must use mcp", errors)
        _ensure(tool.get("project_connection_id") == WORKIQ_CONNECTION, f"work_context must use connection {WORKIQ_CONNECTION}", errors)
        _ensure(tool.get("identity_mode") == "user_entra_token", "work_context must preserve user identity", errors)
    if "bank_policy" in indexed_tools:
        tool = indexed_tools["bank_policy"]
        _ensure(tool.get("type") == "mcp", "bank_policy must use mcp", errors)
        _ensure(tool.get("project_connection_id") == BANK_POLICY_CONNECTION, f"bank_policy must use connection {BANK_POLICY_CONNECTION}", errors)
        _ensure(tool.get("identity_mode") == "connection_managed", "bank_policy must use the verified shared service connection", errors)
        _ensure(tool.get("preserve_user_identity") is False, "bank_policy must not forward user identity", errors)
    if "service_publication" in indexed_tools:
        tool = indexed_tools["service_publication"]
        _ensure(tool.get("type") == "openapi", "service_publication must use openapi", errors)
        _ensure(tool.get("identity_mode") == "project_managed_identity", "service_publication must use project managed identity", errors)
        _ensure(tool.get("require_approval") == "always", "service_publication must require explicit approval", errors)
        auth = tool.get("openapi", {}).get("auth", {})
        _ensure(auth.get("type") == "managed_identity", "service_publication auth must use managed identity", errors)
        _ensure(auth.get("audience") == "https://storage.azure.com/", "service_publication audience must target Azure Storage", errors)
    return errors


def assert_valid_toolbox_manifest(manifest: dict[str, Any]) -> None:
    errors = validate_toolbox_manifest(manifest)
    if errors:
        raise ContractValidationError("\n".join(errors))


def make_azd_toolbox_spec(
    manifest: dict[str, Any],
    *,
    connection_targets: dict[str, str] | None = None,
) -> dict[str, Any]:
    assert_valid_toolbox_manifest(manifest)
    spec = {
        "description": manifest["toolbox"]["description"],
        "tools": [],
    }
    for tool in manifest["tools"]:
        projected = {key: value for key, value in tool.items() if key not in ("identity_mode", "preserve_user_identity")}
        if projected.get("type") in {"mcp", "openapi"}:
            projected.pop("name", None)
        if (
            projected.get("type") == "fabric_iq_preview"
            and isinstance(projected.get("server_url"), str)
            and projected["server_url"].startswith("connection-target://")
        ):
            connection_name = projected.get("project_connection_id")
            if connection_targets and connection_name in connection_targets:
                projected["server_url"] = connection_targets[connection_name]
        spec["tools"].append(projected)
    return spec


def verify_connection_exists(connection_name: str, *, project_endpoint: str = PROJECT_ENDPOINT) -> tuple[bool, str]:
    command = [
        "azd",
        "ai",
        "connection",
        "show",
        connection_name,
        "--project-endpoint",
        project_endpoint,
        "--output",
        "json",
    ]
    completed = subprocess.run(command, capture_output=True, text=True)
    return completed.returncode == 0, completed.stdout or completed.stderr


def get_connection_metadata(connection_name: str, *, project_endpoint: str = PROJECT_ENDPOINT) -> dict[str, Any] | None:
    command = [
        "azd",
        "ai",
        "connection",
        "show",
        connection_name,
        "--project-endpoint",
        project_endpoint,
        "--output",
        "json",
    ]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        return None
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None


def plan_toolbox_setup(
    manifest: dict[str, Any],
    *,
    project_endpoint: str = PROJECT_ENDPOINT,
    spec_output: str | Path | None = None,
) -> dict[str, Any]:
    assert_valid_toolbox_manifest(manifest)
    if project_endpoint != PROJECT_ENDPOINT:
        raise ContractValidationError("project endpoint does not match the verified project endpoint")
    generated_spec_path = Path(spec_output) if spec_output else Path(__file__).with_name("setup_toolbox.generated.spec.json")
    connection_checks = []
    connection_targets: dict[str, str] = {}
    for tool in manifest["tools"]:
        connection_name = tool.get("project_connection_id")
        if not connection_name:
            continue
        exists, detail = verify_connection_exists(connection_name, project_endpoint=project_endpoint)
        metadata = get_connection_metadata(connection_name, project_endpoint=project_endpoint) if exists else None
        if metadata and isinstance(metadata.get("target"), str):
            connection_targets[connection_name] = metadata["target"]
        expected_auth_type = None
        if connection_name in {FABRIC_CONNECTION, WORKIQ_CONNECTION}:
            expected_auth_type = "UserEntraToken"
        elif connection_name == BANK_POLICY_CONNECTION:
            expected_auth_type = "CustomKeys"
        actual_auth_type = metadata.get("authType") if metadata else None
        if expected_auth_type and actual_auth_type and actual_auth_type != expected_auth_type:
            raise ContractValidationError(
                f"connection {connection_name} has authType {actual_auth_type}; expected {expected_auth_type}"
            )
        connection_checks.append(
            {
                "connection_name": connection_name,
                "exists": exists,
                "expected_auth_type": expected_auth_type,
                "actual_auth_type": actual_auth_type,
                "detail": detail.strip(),
            }
        )
    rendered_spec = make_azd_toolbox_spec(manifest, connection_targets=connection_targets)
    return {
        "toolbox_name": manifest["toolbox"]["name"],
        "release_tag": manifest["toolbox"]["release_tag"],
        "project_endpoint": project_endpoint,
        "dry_run": True,
        "generated_spec_path": str(generated_spec_path),
        "rendered_spec": rendered_spec,
        "connection_checks": connection_checks,
        "commands": [
            {
                "description": "Create toolbox if it does not exist",
                "argv": [
                    "azd",
                    "ai",
                    "toolbox",
                    "create",
                    manifest["toolbox"]["name"],
                    "--from-file",
                    str(generated_spec_path),
                    "--project-endpoint",
                    project_endpoint,
                ],
            },
            {
                "description": "Inspect the published toolbox endpoint",
                "argv": [
                    "azd",
                    "ai",
                    "toolbox",
                    "show",
                    manifest["toolbox"]["name"],
                    "--project-endpoint",
                    project_endpoint,
                    "--output",
                    "json",
                ],
            },
        ],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--project-endpoint", default=PROJECT_ENDPOINT)
    parser.add_argument("--output")
    return parser.parse_args(argv)
