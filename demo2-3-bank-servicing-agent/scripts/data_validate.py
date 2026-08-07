from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from data_contract import ContractValidationError, PROJECT_ENDPOINT, assert_valid_manifest, load_json, transition_manifest, write_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate or transition Demo 1 service corpus manifests.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--manifest", required=True)
    validate_parser.add_argument("--repo-root", default=Path(__file__).resolve().parents[2])

    transition_parser = subparsers.add_parser("transition")
    transition_parser.add_argument("--manifest", required=True)
    transition_parser.add_argument("--next-state", required=True)
    transition_parser.add_argument("--if-match", required=True)
    transition_parser.add_argument("--expected-record-version", type=int, required=True)
    transition_parser.add_argument("--actor", default="content.publisher")
    transition_parser.add_argument("--timestamp", default="2026-08-04T14:30:00Z")
    transition_parser.add_argument("--note", default="")
    transition_parser.add_argument("--output")
    transition_parser.add_argument("--allow-write", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            manifest = load_json(args.manifest)
            assert_valid_manifest(manifest, repo_root=args.repo_root)
            print(json.dumps({"ok": True, "manifest": args.manifest, "project_endpoint": PROJECT_ENDPOINT}, indent=2))
            return 0
        manifest = load_json(args.manifest)
        transitioned = transition_manifest(
            manifest,
            args.next_state,
            if_match=args.if_match,
            expected_record_version=args.expected_record_version,
            actor=args.actor,
            note=args.note,
            timestamp=args.timestamp,
        )
        if args.output and args.allow_write:
            write_json(args.output, transitioned)
        print(json.dumps(transitioned, indent=2))
        return 0
    except ContractValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
