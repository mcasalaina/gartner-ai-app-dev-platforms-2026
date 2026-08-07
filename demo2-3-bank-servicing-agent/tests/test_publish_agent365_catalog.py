from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from scripts.publish_agent365_catalog import (
    PublishError,
    build_package,
    main,
    version_tuple,
)


def manifest_dir(tmp_path: Path) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    manifest = {
        "id": "blueprint-id",
        "name": {"short": "Test Agent"},
        "version": "1.0.0",
        "agenticUserTemplates": [{"id": "template-id"}],
    }
    template = {
        "id": "template-id",
        "agentIdentityBlueprintId": "blueprint-id",
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "agenticUserTemplateManifest.json").write_text(
        json.dumps(template),
        encoding="utf-8",
    )
    (tmp_path / "color.png").write_bytes(b"color")
    (tmp_path / "outline.png").write_bytes(b"outline")
    return tmp_path


def test_build_package_is_flat_and_stamps_version(tmp_path: Path) -> None:
    source = manifest_dir(tmp_path / "source")
    output = tmp_path / "manifest.zip"

    manifest = build_package(source, output, "2.0.1")

    assert manifest["version"] == "2.0.1"
    with zipfile.ZipFile(output) as package:
        assert set(package.namelist()) == {
            "manifest.json",
            "agenticUserTemplateManifest.json",
            "color.png",
            "outline.png",
        }
        packaged_manifest = json.loads(package.read("manifest.json"))
    assert packaged_manifest["version"] == "2.0.1"


def test_build_package_rejects_mismatched_blueprint(tmp_path: Path) -> None:
    source = manifest_dir(tmp_path)
    template_path = source / "agenticUserTemplateManifest.json"
    template = json.loads(template_path.read_text(encoding="utf-8"))
    template["agentIdentityBlueprintId"] = "other-blueprint"
    template_path.write_text(json.dumps(template), encoding="utf-8")

    with pytest.raises(PublishError, match="blueprint IDs"):
        build_package(source, tmp_path / "manifest.zip", "1.0.0")


def test_version_tuple_rejects_invalid_version() -> None:
    with pytest.raises(PublishError, match="major.minor.patch"):
        version_tuple("1.0")


def test_main_packages_source_version(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = manifest_dir(tmp_path / "source")

    assert main(["--manifest-dir", str(source)]) == 0

    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "packaged"
    assert result["version"] == "1.0.0"
    assert result["uploadUrl"] == "https://admin.cloud.microsoft/?#/agents/all"
    assert (source / "manifest.zip").is_file()
