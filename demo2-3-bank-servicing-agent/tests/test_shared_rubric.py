from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SharedRubricTests(unittest.TestCase):
    def test_foundry_and_assert_use_the_same_dimensions_weights_and_gates(self) -> None:
        foundry = json.loads(
            (
                ROOT
                / "evaluation"
                / "foundry"
                / "evaluators"
                / "bank_servicing_rubric.v2.json"
            ).read_text(encoding="utf-8")
        )
        assert_policy = json.loads(
            (
                ROOT
                / "evaluation"
                / "assert"
                / "policies"
                / "rubric-policy.json"
            ).read_text(encoding="utf-8")
        )

        foundry_contract = {
            item["id"]: (item["weight_points"], item["hard_gate"])
            for item in foundry["dimensions"]
        }
        assert_contract = {
            item["name"]: (item["weight"], item["hard_gate"])
            for item in assert_policy["dimensions"]
        }

        self.assertEqual(foundry_contract, assert_contract)
        self.assertEqual(assert_policy["pass_threshold"], foundry["scoring"]["pass_threshold"])


if __name__ == "__main__":
    unittest.main()
