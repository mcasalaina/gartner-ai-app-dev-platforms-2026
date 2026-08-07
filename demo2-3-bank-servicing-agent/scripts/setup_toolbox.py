from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from data_contract import (
    ContractValidationError,
    PROJECT_ENDPOINT,
    assert_valid_toolbox_manifest,
    load_json,
    plan_toolbox_setup,
    write_json,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and plan setup for bank-servicing-agent-tools.")
    parser.add_argument("--manifest", default=Path(__file__).resolve().parents[1] / "src" / "bank-servicing-agent" / "toolbox.yaml")
    parser.add_argument("--project-endpoint", default=PROJECT_ENDPOINT)
    parser.add_argument("--spec-output", default=Path(__file__).with_name("setup_toolbox.generated.spec.json"))
    parser.add_argument("--output")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--allow-remote-mutation", action="store_true")
    args = parser.parse_args(argv)

    try:
        manifest = load_json(args.manifest)
        assert_valid_toolbox_manifest(manifest)
        plan = plan_toolbox_setup(manifest, project_endpoint=args.project_endpoint, spec_output=args.spec_output)
        write_json(args.spec_output, plan["rendered_spec"])
        if args.apply:
            if not args.allow_remote_mutation:
                raise ContractValidationError("Refusing remote mutation without --allow-remote-mutation.")
            create_command = plan["commands"][0]["argv"]
            completed = subprocess.run(create_command, capture_output=True, text=True)
            plan["dry_run"] = False
            plan["apply_result"] = {
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
            if completed.returncode != 0:
                raise ContractValidationError(
                    f"azd ai toolbox create failed: {completed.stderr.strip() or completed.stdout.strip()}"
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
