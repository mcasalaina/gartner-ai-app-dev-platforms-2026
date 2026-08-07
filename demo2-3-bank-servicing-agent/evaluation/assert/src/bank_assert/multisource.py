from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from bank_assert.target import Agent365Target

INTRO_QUERY = (
    "I'm preparing to follow up with Maria Garcia about the $35 ATM fee on her checking "
    "account ending in 1013. Tell me what happened, whether the fee is eligible for a refund, "
    "whether anyone must approve it, and whether Maria has sent me a recent message about it."
)
REQUIRED_SOURCES = ("Fabric IQ", "Foundry IQ", "Work IQ")
EXACT_SOURCES_LINE = "Sources used: Fabric IQ, Foundry IQ, Work IQ"
_SOURCE_LINE = re.compile(r"(?im)^\s*Sources used:\s*([^\r\n]+)\s*$")


@dataclass(frozen=True)
class MultiSourceResult:
    passed: bool
    hard_failure: bool
    timestamp: str
    run_id: str
    agent_name: str
    agent_version: str
    query: str
    required_sources: tuple[str, ...]
    returned_sources: tuple[str, ...]
    source_line: str | None
    response_sha256: str
    failures: tuple[str, ...]


async def run_multisource_case(output: Path, summary: Path) -> MultiSourceResult:
    target = Agent365Target()
    response = await target.chat(INTRO_QUERY, [{"role": "user", "content": INTRO_QUERY}])
    returned = frozenset(getattr(target, "last_grounding_sources", frozenset()))
    lines = _SOURCE_LINE.findall(response)
    source_line = f"Sources used: {lines[0].strip()}" if len(lines) == 1 else None
    claimed = (
        {source.strip() for source in lines[0].split(",") if source.strip()}
        if len(lines) == 1
        else set()
    )
    failures: list[str] = []
    missing = sorted(set(REQUIRED_SOURCES) - returned)
    if missing:
        failures.append(f"Required tools returned no data: {', '.join(missing)}")
    if len(lines) != 1:
        failures.append(f"Expected exactly one Sources used line; found {len(lines)}")
    elif source_line != EXACT_SOURCES_LINE:
        failures.append(f"Sources line mismatch: {source_line!r}")
    unsupported = sorted(claimed - returned)
    if unsupported:
        failures.append(f"Sources claimed without successful tool data: {', '.join(unsupported)}")

    result = MultiSourceResult(
        passed=not failures,
        hard_failure=bool(failures),
        timestamp=datetime.now(UTC).isoformat(),
        run_id=os.getenv("ASSERT_RUN_ID", ""),
        agent_name=os.getenv("FOUNDRY_AGENT_NAME", ""),
        agent_version=os.getenv("FOUNDRY_AGENT_VERSION", ""),
        query=INTRO_QUERY,
        required_sources=REQUIRED_SOURCES,
        returned_sources=tuple(source for source in REQUIRED_SOURCES if source in returned),
        source_line=source_line,
        response_sha256=hashlib.sha256(response.encode()).hexdigest(),
        failures=tuple(failures),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(asdict(result), indent=2) + "\n", encoding="utf-8")
    summary.write_text(
        "\n".join(
            (
                "# Multi-source intro evaluation",
                "",
                f"- Timestamp: `{result.timestamp}`",
                f"- Run ID: `{result.run_id}`",
                f"- Agent: `{result.agent_name}` version `{result.agent_version}`",
                f"- Passed: `{str(result.passed).lower()}`",
                f"- Hard failure: `{str(result.hard_failure).lower()}`",
                f"- Required sources: `{', '.join(result.required_sources)}`",
                f"- Successful tool evidence: `{', '.join(result.returned_sources) or 'none'}`",
                f"- Observed source line: `{result.source_line or 'missing'}`",
                f"- Response SHA-256: `{result.response_sha256}`",
                "",
                "## Failures",
                "",
                *(f"- {failure}" for failure in result.failures),
                "" if result.failures else "- None",
                "",
                "The response body is intentionally not persisted because Work IQ may return "
                "workplace content. A source is counted only when the remote response includes a "
                "successful, non-empty MCP tool result for that source.",
                "",
            )
        ),
        encoding="utf-8",
    )
    return result
