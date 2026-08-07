from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "demo2-3-bank-servicing-agent" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from data_contract import PROJECT_ENDPOINT, compute_manifest_etag, load_json, validate_manifest, validate_toolbox_manifest


class ContentContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.content_root = ROOT / "demo2-3-bank-servicing-agent" / "content"
        self.seeds = self.content_root / "seeds"
        self.toolbox_manifest = ROOT / "demo2-3-bank-servicing-agent" / "src" / "bank-servicing-agent" / "toolbox.yaml"

    def test_seed_manifests_validate(self) -> None:
        for manifest_name in [
            "demo1-service-corpus-draft.json",
            "demo1-service-corpus-qc-failed.json",
            "demo1-service-corpus-approved.json",
            "demo1-service-corpus-published.json",
        ]:
            manifest = load_json(self.seeds / manifest_name)
            self.assertEqual([], validate_manifest(manifest, repo_root=ROOT), manifest_name)

    def test_transition_enforces_etag_and_version(self) -> None:
        manifest_path = self.seeds / "demo1-service-corpus-draft.json"
        manifest = load_json(manifest_path)
        completed = subprocess.run(
            [
                "python3",
                str(SCRIPTS / "data_validate.py"),
                "transition",
                "--manifest",
                str(manifest_path),
                "--next-state",
                "pending_review",
                "--if-match",
                compute_manifest_etag(manifest),
                "--expected-record-version",
                str(manifest["record_version"]),
                "--actor",
                "test.runner",
                "--timestamp",
                "2026-08-04T15:00:00Z",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        transitioned = json.loads(completed.stdout)
        self.assertEqual("pending_review", transitioned["review"]["state"])
        self.assertEqual(manifest["record_version"] + 1, transitioned["record_version"])
        self.assertNotEqual(manifest["etag"], transitioned["etag"])

    def test_invalid_transition_is_rejected(self) -> None:
        manifest_path = self.seeds / "demo1-service-corpus-approved.json"
        manifest = load_json(manifest_path)
        completed = subprocess.run(
            [
                "python3",
                str(SCRIPTS / "data_validate.py"),
                "transition",
                "--manifest",
                str(manifest_path),
                "--next-state",
                "draft",
                "--if-match",
                compute_manifest_etag(manifest),
                "--expected-record-version",
                str(manifest["record_version"]),
            ],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("invalid lifecycle transition", completed.stderr)

    def test_publish_plan_is_separate_from_policy_kb(self) -> None:
        manifest_path = self.seeds / "demo1-service-corpus-approved.json"
        completed = subprocess.run(
            [
                "python3",
                str(SCRIPTS / "data_publish_plan.py"),
                "--manifest",
                str(manifest_path),
                "--project-endpoint",
                PROJECT_ENDPOINT,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        plan = json.loads(completed.stdout)
        self.assertTrue(plan["dry_run"])
        self.assertEqual("foundry_iq", plan["steps"][-1]["target"])
        self.assertNotEqual("kb-acme-bank-foundryiq", plan["steps"][-1]["payload"]["connection_name"])

    def test_toolbox_manifest_validates(self) -> None:
        manifest = load_json(self.toolbox_manifest)
        self.assertEqual([], validate_toolbox_manifest(manifest))


if __name__ == "__main__":
    unittest.main()
