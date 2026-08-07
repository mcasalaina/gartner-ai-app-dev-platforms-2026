from __future__ import annotations

import argparse
import json
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-endpoint", required=True)
    parser.add_argument("--eval-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    project = AIProjectClient(
        endpoint=args.project_endpoint,
        credential=DefaultAzureCredential(),
    )
    client = project.get_openai_client()
    run = client.evals.runs.retrieve(run_id=args.run_id, eval_id=args.eval_id)
    items = [
        item.model_dump()
        for item in client.evals.runs.output_items.list(
            run_id=args.run_id,
            eval_id=args.eval_id,
        )
    ]
    payload = {
        "eval": client.evals.retrieve(args.eval_id).model_dump(),
        "run": run.model_dump(),
        "output_items": items,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": run.status, "items": len(items), "output": str(args.output)}))


if __name__ == "__main__":
    main()
