from __future__ import annotations

from pathlib import Path

from bank_servicing_agent.eval_assets import (
    gate_multisource_evidence,
    gate_suite_result,
    load_asset_manifest,
    load_rubric,
    validate_dataset_case,
    validate_repository_assets,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
AGENT_ROOT = REPO_ROOT / 'src' / 'bank-servicing-agent'
EVALUATION_ROOT = REPO_ROOT / 'evaluation' / 'foundry'


def test_repository_assets_validate_cleanly() -> None:
    assert validate_repository_assets(AGENT_ROOT, EVALUATION_ROOT) == []


def test_gate_suite_result_fails_on_hard_gate_failure() -> None:
    manifest = load_asset_manifest(EVALUATION_ROOT / 'asset-manifest.yaml')
    rubric = load_rubric(EVALUATION_ROOT / 'evaluators' / 'bank_servicing_rubric.v2.json')

    result = gate_suite_result(
        'dlp-guardrails',
        {
            'aggregate': 1.0,
            'dimensions': {
                'privacy_glba_regulation_p': 0.0,
                'authorized_customer_and_service_scope': 1.0,
            },
        },
        manifest,
        rubric,
    )

    assert result.passed is False
    assert any(failure.code == 'hard_gate_failure' for failure in result.failures)


def test_gate_suite_result_fails_on_aggregate_regression() -> None:
    manifest = load_asset_manifest(EVALUATION_ROOT / 'asset-manifest.yaml')
    rubric = load_rubric(EVALUATION_ROOT / 'evaluators' / 'bank_servicing_rubric.v2.json')

    result = gate_suite_result(
        'regression-core',
        {
            'aggregate': 0.87,
            'previous_aggregate': 0.93,
            'dimensions': {
                'authorized_customer_and_service_scope': 1.0,
                'bsa_aml_cip_and_ofac_controls': 1.0,
                'regulation_e_error_resolution': 1.0,
                'deposit_disclosures_funds_availability_and_fdic': 1.0,
                'privacy_glba_regulation_p': 1.0,
                'fair_treatment_fcra_and_udaap': 1.0,
                'servicing_authority_and_human_approval': 1.0,
                'source_routing_and_evidence_provenance': 1.0,
                'security_and_instruction_integrity': 1.0,
            },
        },
        manifest,
        rubric,
    )

    assert result.passed is False
    assert {failure.code for failure in result.failures} >= {'aggregate_regression', 'aggregate_below_regression_floor'}


def test_validate_dataset_case_rejects_missing_and_malformed_fields() -> None:
    rubric = load_rubric(EVALUATION_ROOT / 'evaluators' / 'bank_servicing_rubric.v2.json')
    rubric_ids = {dimension['id'] for dimension in rubric['dimensions']}
    bad_case = {
        'case_id': 'broken',
        'suite_id': 'smoke-core',
        'mode': 'customer_servicing',
        'query': '',
        'expected_behavior': '',
        'non_production_data_only': False,
        'applicable_dimensions': ['privacy_glba_regulation_p'],
        'hard_gate_dimensions': ['unknown_dimension'],
        'tags': [],
    }

    errors = validate_dataset_case(bad_case, rubric_ids)

    assert any('non_production_data_only=true' in error for error in errors)
    assert any('non-empty query' in error for error in errors)
    assert any('unknown hard-gate dimensions' in error for error in errors)


def test_multisource_gate_requires_tool_evidence_and_exact_line() -> None:
    passed = gate_multisource_evidence(
        'Grounded response.\n\nSources used: Fabric IQ, Foundry IQ, Work IQ',
        {'Fabric IQ', 'Foundry IQ', 'Work IQ'},
    )
    assert passed.passed is True

    failed = gate_multisource_evidence(
        'Grounded response.\n\nSources used: Fabric IQ, Foundry IQ, Work IQ',
        {'Fabric IQ', 'Foundry IQ'},
    )
    assert failed.passed is False
    assert {failure.code for failure in failed.failures} == {
        'missing_required_tool_evidence',
        'unsupported_source_claim',
    }
