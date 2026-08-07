from __future__ import annotations

import argparse
import json
import sys

from data_contract import (
    BANK_POLICY_CONNECTION,
    ContractValidationError,
    PROJECT_ENDPOINT,
    SERVICE_CORPUS_CONNECTION,
    build_publish_plan,
    load_json,
    write_json,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a dry-run publish plan for the Demo 1 service corpus.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--project-endpoint", default=PROJECT_ENDPOINT)
    parser.add_argument("--foundry-iq-connection", default=SERVICE_CORPUS_CONNECTION)
    parser.add_argument("--blob-container")
    parser.add_argument("--output")
    parser.add_argument("--allow-remote-mutation", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    try:
        manifest = load_json(args.manifest)
        if args.foundry_iq_connection == BANK_POLICY_CONNECTION:
            raise ContractValidationError("The bank policy connection is reserved and cannot be used for Demo 1 service publishing.")
        plan = build_publish_plan(
            manifest,
            source_manifest=args.manifest,
            project_endpoint=args.project_endpoint,
            foundry_iq_connection_name=args.foundry_iq_connection,
            blob_container=args.blob_container,
            dry_run=not (args.allow_remote_mutation and args.apply),
            allow_remote_mutation=args.allow_remote_mutation,
            apply=args.apply,
        )
        if args.output:
            write_json(args.output, plan)
        print(json.dumps(plan, indent=2))
        return 0
    except ContractValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
