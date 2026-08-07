from __future__ import annotations

import argparse
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

ADMIN_CENTER_URL = "https://admin.cloud.microsoft/?#/agents/all"
PACKAGE_FILES = (
    "manifest.json",
    "agenticUserTemplateManifest.json",
    "color.png",
    "outline.png",
)


class PublishError(RuntimeError):
    pass


def version_tuple(version: str) -> tuple[int, int, int]:
    parts = version.split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise PublishError(f"Manifest version must use major.minor.patch: {version}")
    return int(parts[0]), int(parts[1]), int(parts[2])


def build_package(
    manifest_dir: Path,
    output_path: Path,
    version: str,
) -> dict[str, Any]:
    version_tuple(version)
    missing = [name for name in PACKAGE_FILES if not (manifest_dir / name).is_file()]
    if missing:
        raise PublishError(f"Manifest package is missing: {', '.join(missing)}")

    manifest = json.loads((manifest_dir / "manifest.json").read_text(encoding="utf-8"))
    template = json.loads(
        (manifest_dir / "agenticUserTemplateManifest.json").read_text(
            encoding="utf-8"
        )
    )
    external_id = str(manifest.get("id") or "")
    templates = manifest.get("agenticUserTemplates") or []
    if not external_id or len(templates) != 1:
        raise PublishError("Manifest must define one Agent 365 template")
    if template.get("agentIdentityBlueprintId") != external_id:
        raise PublishError("Manifest and template blueprint IDs do not match")
    if templates[0].get("id") != template.get("id"):
        raise PublishError("Manifest and template IDs do not match")

    manifest["version"] = version
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        temporary_dir = Path(temporary)
        (temporary_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        for name in PACKAGE_FILES[1:]:
            (temporary_dir / name).write_bytes((manifest_dir / name).read_bytes())
        with zipfile.ZipFile(
            output_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
        ) as package:
            for name in PACKAGE_FILES:
                package.write(temporary_dir / name, arcname=name)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Package Bank Servicing Agent Template for supported upload through the "
            "Microsoft 365 admin center."
        )
    )
    parser.add_argument("--manifest-dir", type=Path, required=True)
    parser.add_argument("--version")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    try:
        source_manifest = json.loads(
            (args.manifest_dir / "manifest.json").read_text(encoding="utf-8")
        )
        version = args.version or str(source_manifest["version"])
        package_path = args.output or args.manifest_dir / "manifest.zip"
        packaged_manifest = build_package(args.manifest_dir, package_path, version)
        print(
            json.dumps(
                {
                    "status": "packaged",
                    "externalId": packaged_manifest["id"],
                    "displayName": packaged_manifest["name"]["short"],
                    "version": packaged_manifest["version"],
                    "package": str(package_path),
                    "uploadUrl": ADMIN_CENTER_URL,
                    "nextStep": (
                        "Open Agents > All agents > Registry, select the existing "
                        "agent, choose Update in store, and upload this package."
                    ),
                },
                indent=2,
            )
        )
        return 0
    except (KeyError, OSError, PublishError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
