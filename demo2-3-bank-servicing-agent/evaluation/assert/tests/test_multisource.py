from __future__ import annotations

import json
from pathlib import Path

import pytest

from bank_assert.multisource import run_multisource_case


@pytest.mark.asyncio
async def test_multisource_case_passes_only_with_all_tool_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeTarget:
        last_grounding_sources = frozenset({"Fabric IQ", "Foundry IQ", "Work IQ"})

        async def chat(self, message: str, history: list[dict[str, str]]) -> str:
            return "Grounded answer.\n\nSources used: Fabric IQ, Foundry IQ, Work IQ"

    monkeypatch.setattr("bank_assert.multisource.Agent365Target", FakeTarget)
    output = tmp_path / "result.json"
    summary = tmp_path / "summary.md"
    result = await run_multisource_case(output, summary)

    assert result.passed is True
    assert json.loads(output.read_text())["hard_failure"] is False
    assert "Grounded answer" not in summary.read_text()


@pytest.mark.asyncio
async def test_multisource_case_hard_fails_unsupported_claim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeTarget:
        last_grounding_sources = frozenset({"Fabric IQ", "Foundry IQ"})

        async def chat(self, message: str, history: list[dict[str, str]]) -> str:
            return "Grounded answer.\n\nSources used: Fabric IQ, Foundry IQ, Work IQ"

    monkeypatch.setattr("bank_assert.multisource.Agent365Target", FakeTarget)
    result = await run_multisource_case(tmp_path / "result.json", tmp_path / "summary.md")

    assert result.passed is False
    assert result.hard_failure is True
    assert any("Work IQ" in failure for failure in result.failures)
