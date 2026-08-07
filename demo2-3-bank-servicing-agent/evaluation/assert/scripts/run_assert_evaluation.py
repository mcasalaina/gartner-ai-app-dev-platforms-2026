#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

EVALUATION_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVALUATION_ROOT / "src"))

if __name__ == "__main__":
    from bank_assert.cli import main

    main()
