from __future__ import annotations

from pathlib import Path

from bank_servicing_agent.eval_assets import validate_repository_assets


def main() -> int:
    repo_root = Path(__file__).resolve().parents[3]
    agent_root = repo_root / 'src' / 'bank-servicing-agent'
    evaluation_root = repo_root / 'evaluation' / 'foundry'
    errors = validate_repository_assets(agent_root, evaluation_root)
    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1
    print('Foundry evaluation and optimizer assets validated successfully.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
