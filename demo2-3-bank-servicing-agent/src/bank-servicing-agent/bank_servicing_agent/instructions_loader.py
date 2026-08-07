from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from bank_servicing_agent.models import InstructionBundle

_VERSION_PATTERN = re.compile(r"^Instruction-Version:\s*(?P<version>\S+)\s*$")


@dataclass(frozen=True, slots=True)
class OptimizerConfigBundle:
    composed_instructions: str
    raw: Any


def load_versioned_instructions(path: Path) -> InstructionBundle:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        match = _VERSION_PATTERN.match(line.strip())
        if not match:
            raise RuntimeError(
                f"The first non-empty line in {path} must declare Instruction-Version: <version>"
            )
        body = "\n".join(lines[index + 1 :]).strip()
        if not body:
            raise RuntimeError(f"No instruction body found in {path}")
        return InstructionBundle(version=match.group("version"), body=body)
    raise RuntimeError(f"Instruction file is empty: {path}")


def load_optimizer_bundle() -> OptimizerConfigBundle:
    from azure.ai.agentserver.optimization import load_config

    config = load_config()
    return OptimizerConfigBundle(
        composed_instructions=config.compose_instructions(),
        raw=config,
    )


def load_runtime_instructions(path: Path) -> InstructionBundle:
    versioned = load_versioned_instructions(path)
    optimizer_bundle = load_optimizer_bundle()
    composed = optimizer_bundle.composed_instructions.strip()
    if not composed:
        raise RuntimeError("Agent optimizer configuration returned empty instructions")
    return InstructionBundle(version=versioned.version, body=composed)
