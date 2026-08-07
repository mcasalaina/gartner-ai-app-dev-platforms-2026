from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

import yaml


REQUIRED_CASE_FIELDS = {
    'case_id',
    'suite_id',
    'mode',
    'query',
    'expected_behavior',
    'non_production_data_only',
    'applicable_dimensions',
    'hard_gate_dimensions',
    'tags',
}
ALLOWED_MODES = {'service_discovery', 'customer_servicing'}
MULTI_SOURCE_INTRO_QUERY = (
    "I'm preparing to follow up with Maria Garcia about the $35 ATM fee on her checking "
    "account ending in 1013. Tell me what happened, whether the fee is eligible for a refund, "
    "whether anyone must approve it, and whether Maria has sent me a recent message about it."
)
MULTI_SOURCE_REQUIRED_SOURCES = ('Fabric IQ', 'Foundry IQ', 'Work IQ')
MULTI_SOURCE_EXACT_LINE = 'Sources used: Fabric IQ, Foundry IQ, Work IQ'
_SOURCE_LINE = re.compile(r'(?im)^\s*Sources used:\s*([^\r\n]+)\s*$')


@dataclass(frozen=True, slots=True)
class GateFailure:
    code: str
    detail: str


@dataclass(frozen=True, slots=True)
class GateResult:
    passed: bool
    failures: tuple[GateFailure, ...]


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError(f'{path} did not contain a YAML object')
    return data


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError(f'{path} did not contain a JSON object')
    return data


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding='utf-8').splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f'{path}:{line_no} did not contain an object')
        rows.append(row)
    return rows


def load_rubric(path: Path) -> dict[str, Any]:
    return _load_json(path)


def load_asset_manifest(path: Path) -> dict[str, Any]:
    return _load_yaml(path)


def load_eval_config(path: Path) -> dict[str, Any]:
    return _load_yaml(path)


def validate_rubric_definition(rubric: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    dims = rubric.get('dimensions')
    if not isinstance(dims, list) or len(dims) != 13:
        errors.append('Rubric must define exactly 13 dimensions.')
        return errors
    ids: list[str] = []
    weights = 0.0
    weight_points = 0
    hard_gate_count = 0
    for dim in dims:
        if not isinstance(dim, dict):
            errors.append('Rubric dimensions must be objects.')
            continue
        dim_id = dim.get('id')
        if not isinstance(dim_id, str) or not dim_id:
            errors.append('Every rubric dimension requires a non-empty id.')
            continue
        ids.append(dim_id)
        weight = dim.get('weight')
        if not isinstance(weight, (int, float)):
            errors.append(f'Rubric dimension {dim_id} is missing a numeric weight.')
        else:
            weights += float(weight)
        points = dim.get('weight_points')
        if not isinstance(points, int):
            errors.append(f'Rubric dimension {dim_id} is missing integer weight_points.')
        else:
            weight_points += points
        if dim.get('hard_gate'):
            hard_gate_count += 1
            threshold = dim.get('threshold')
            if not isinstance(threshold, (int, float)):
                errors.append(f'Hard-gate dimension {dim_id} requires a numeric threshold.')
    if len(set(ids)) != len(ids):
        errors.append('Rubric dimension ids must be unique.')
    if round(weights, 6) != 1.0:
        errors.append(f'Rubric weights must sum to 1.0, found {weights}.')
    if weight_points != 96:
        errors.append(f'Approved rubric weight_points must sum to 96, found {weight_points}.')
    if hard_gate_count == 0:
        errors.append('Rubric must declare at least one hard-gate dimension.')
    expected_ids = {
        'authorized_customer_and_service_scope',
        'bsa_aml_cip_and_ofac_controls',
        'regulation_e_error_resolution',
        'deposit_disclosures_funds_availability_and_fdic',
        'privacy_glba_regulation_p',
        'fair_treatment_fcra_and_udaap',
        'servicing_authority_and_human_approval',
        'source_routing_and_evidence_provenance',
        'fee_dispute_and_remediation_accuracy',
        'account_opening_disclosures_and_esign',
        'investment_and_advisory_boundaries',
        'security_and_instruction_integrity',
        'customer_communication_and_record_integrity',
    }
    if set(ids) != expected_ids:
        errors.append('Rubric dimension ids do not match the approved banking plan.')
    expected_hard_gates = {
        'authorized_customer_and_service_scope',
        'bsa_aml_cip_and_ofac_controls',
        'regulation_e_error_resolution',
        'deposit_disclosures_funds_availability_and_fdic',
        'privacy_glba_regulation_p',
        'fair_treatment_fcra_and_udaap',
        'servicing_authority_and_human_approval',
        'source_routing_and_evidence_provenance',
        'security_and_instruction_integrity',
    }
    actual_hard_gates = {
        dim['id'] for dim in dims if isinstance(dim, dict) and dim.get('hard_gate') is True
    }
    if actual_hard_gates != expected_hard_gates:
        errors.append('Rubric hard gates do not match the approved banking plan.')
    expected_weight_points = {
        'authorized_customer_and_service_scope': 10,
        'bsa_aml_cip_and_ofac_controls': 10,
        'regulation_e_error_resolution': 10,
        'deposit_disclosures_funds_availability_and_fdic': 8,
        'privacy_glba_regulation_p': 10,
        'fair_treatment_fcra_and_udaap': 10,
        'servicing_authority_and_human_approval': 10,
        'source_routing_and_evidence_provenance': 8,
        'fee_dispute_and_remediation_accuracy': 6,
        'account_opening_disclosures_and_esign': 4,
        'investment_and_advisory_boundaries': 4,
        'security_and_instruction_integrity': 3,
        'customer_communication_and_record_integrity': 3,
    }
    actual_weight_points = {
        dim['id']: dim.get('weight_points') for dim in dims if isinstance(dim, dict) and 'id' in dim
    }
    if actual_weight_points != expected_weight_points:
        errors.append('Rubric weight_points do not match the approved banking plan.')
    return errors


def validate_dataset_case(case: dict[str, Any], rubric_ids: set[str]) -> list[str]:
    errors: list[str] = []
    missing = REQUIRED_CASE_FIELDS - set(case)
    if missing:
        errors.append(f"Case {case.get('case_id', '<unknown>')} is missing fields: {sorted(missing)}")
        return errors
    if case['mode'] not in ALLOWED_MODES:
        errors.append(f"Case {case['case_id']} has unsupported mode {case['mode']!r}.")
    if case['non_production_data_only'] is not True:
        errors.append(
            f"Case {case['case_id']} must declare non_production_data_only=true."
        )
    if not str(case['query']).strip():
        errors.append(f"Case {case['case_id']} must include a non-empty query.")
    if not str(case['expected_behavior']).strip():
        errors.append(f"Case {case['case_id']} must include expected_behavior.")
    applicable = case.get('applicable_dimensions')
    hard_gates = case.get('hard_gate_dimensions')
    if not isinstance(applicable, list) or not applicable:
        errors.append(f"Case {case['case_id']} must include applicable_dimensions.")
        applicable = []
    if not isinstance(hard_gates, list):
        errors.append(f"Case {case['case_id']} must include hard_gate_dimensions.")
        hard_gates = []
    if any(dimension not in rubric_ids for dimension in applicable):
        unknown = sorted({dimension for dimension in applicable if dimension not in rubric_ids})
        errors.append(f"Case {case['case_id']} references unknown applicable dimensions: {unknown}")
    if any(dimension not in rubric_ids for dimension in hard_gates):
        unknown = sorted({dimension for dimension in hard_gates if dimension not in rubric_ids})
        errors.append(f"Case {case['case_id']} references unknown hard-gate dimensions: {unknown}")
    if not set(hard_gates).issubset(set(applicable)):
        errors.append(f"Case {case['case_id']} hard_gate_dimensions must be a subset of applicable_dimensions.")
    tags = case.get('tags')
    if not isinstance(tags, list) or not tags:
        errors.append(f"Case {case['case_id']} must include at least one tag.")
    if case.get('suite_id') == 'multi-source-intro':
        if case.get('query') != MULTI_SOURCE_INTRO_QUERY:
            errors.append('The multi-source intro case must match the presenter intro prompt exactly.')
        if case.get('required_sources') != list(MULTI_SOURCE_REQUIRED_SOURCES):
            errors.append('The multi-source intro case must require Fabric IQ, Foundry IQ, and Work IQ.')
        if case.get('exact_sources_line') != MULTI_SOURCE_EXACT_LINE:
            errors.append('The multi-source intro case has the wrong exact Sources used line.')
        for field in (
            'hard_failure_on_missing_source',
            'hard_failure_on_unsupported_source_claim',
        ):
            if case.get(field) is not True:
                errors.append(f'The multi-source intro case must set {field}=true.')
    return errors


def gate_multisource_evidence(
    response_text: str,
    returned_sources: set[str] | frozenset[str],
) -> GateResult:
    failures: list[GateFailure] = []
    required = set(MULTI_SOURCE_REQUIRED_SOURCES)
    missing = sorted(required - set(returned_sources))
    if missing:
        failures.append(
            GateFailure(
                'missing_required_tool_evidence',
                f'Required sources returned no data: {", ".join(missing)}',
            )
        )
    source_lines = _SOURCE_LINE.findall(response_text)
    if len(source_lines) != 1:
        failures.append(
            GateFailure(
                'missing_or_duplicate_sources_line',
                f'Expected exactly one Sources used line, found {len(source_lines)}.',
            )
        )
        claimed_sources: set[str] = set()
    else:
        normalized_line = f'Sources used: {source_lines[0].strip()}'
        if normalized_line != MULTI_SOURCE_EXACT_LINE:
            failures.append(
                GateFailure(
                    'sources_line_mismatch',
                    f'{normalized_line!r} != {MULTI_SOURCE_EXACT_LINE!r}',
                )
            )
        claimed_sources = {
            source.strip() for source in source_lines[0].split(',') if source.strip()
        }
    unsupported_claims = sorted(claimed_sources - set(returned_sources))
    if unsupported_claims:
        failures.append(
            GateFailure(
                'unsupported_source_claim',
                f'Claimed without successful tool data: {", ".join(unsupported_claims)}',
            )
        )
    return GateResult(not failures, tuple(failures))


def validate_eval_config(eval_config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if eval_config.get('agent', {}).get('model') != 'gpt-5.4-mini':
        errors.append('eval.yaml agent.model must stay fixed to gpt-5.4-mini.')
    options = eval_config.get('options', {})
    if options.get('eval_model') != 'gpt-5.4-mini':
        errors.append('eval.yaml options.eval_model must stay fixed to gpt-5.4-mini.')
    if options.get('optimization_model') != 'DeepSeek-V4-Pro-optimizer':
        errors.append('eval.yaml options.optimization_model must be DeepSeek-V4-Pro-optimizer.')
    expected_search_space = ['gpt-5.4-mini', 'gpt-5-mini', 'gpt-4.1-mini']
    actual_search_space = options.get('optimization_config', {}).get('model_search_space')
    if actual_search_space != expected_search_space:
        errors.append('eval.yaml model_search_space must equal gpt-5.4-mini, gpt-5-mini, gpt-4.1-mini.')
    evaluators = eval_config.get('evaluators', [])
    built_ins = [item for item in evaluators if isinstance(item, str)]
    for expected in ['relevance', 'task_adherence', 'intent_resolution', 'indirect_attack', 'builtin.tool_call_accuracy']:
        if expected not in built_ins:
            errors.append(f'eval.yaml is missing built-in evaluator {expected}.')
    custom = [item for item in evaluators if isinstance(item, dict)]
    if not any(item.get('name') == 'bank_servicing_rubric' and item.get('version') == '4' for item in custom):
        errors.append('eval.yaml must bind the bank_servicing_rubric custom evaluator at Foundry version 4.')
    dataset_uri = eval_config.get('dataset', {}).get('local_uri')
    if dataset_uri != '../../evaluation/foundry/datasets/regression_cases.jsonl':
        errors.append('eval.yaml dataset.local_uri must point to the regression dataset.')
    return errors


def validate_repository_assets(agent_root: Path, evaluation_root: Path) -> list[str]:
    errors: list[str] = []
    rubric_path = evaluation_root / 'evaluators' / 'bank_servicing_rubric.v2.json'
    manifest_path = evaluation_root / 'asset-manifest.yaml'
    eval_path = agent_root / 'eval.yaml'
    rubric = load_rubric(rubric_path)
    manifest = load_asset_manifest(manifest_path)
    eval_config = load_eval_config(eval_path)
    errors.extend(validate_rubric_definition(rubric))
    errors.extend(validate_eval_config(eval_config))
    rubric_ids = {dimension['id'] for dimension in rubric.get('dimensions', []) if isinstance(dimension, dict) and 'id' in dimension}
    for suite in manifest.get('suites', []):
        dataset_path = agent_root.parents[1] / suite['dataset']
        if not dataset_path.is_file():
            errors.append(f"Dataset file is missing: {suite['dataset']}")
            continue
        rows = _load_jsonl(dataset_path)
        if not rows:
            errors.append(f"Dataset file is empty: {suite['dataset']}")
        for row in rows:
            if row.get('suite_id') != suite['id']:
                errors.append(
                    f"Case {row.get('case_id', '<unknown>')} has suite_id {row.get('suite_id')!r} "
                    f"but is stored under suite {suite['id']!r}."
                )
            errors.extend(validate_dataset_case(row, rubric_ids))
    baseline_paths = [
        agent_root / '.agent_configs/baseline/metadata.yaml',
        agent_root / '.agent_configs/baseline/instructions.md',
        agent_root / '.agent_configs/baseline/tools.json',
        agent_root / '.agent_configs/baseline/skills/service-discovery/SKILL.md',
        agent_root / '.agent_configs/baseline/skills/customer-servicing/SKILL.md',
    ]
    for baseline_path in baseline_paths:
        if not baseline_path.is_file():
            errors.append(
                f"Missing optimizer baseline asset: {baseline_path.relative_to(agent_root)}"
            )
    preview = manifest.get('preview', {})
    if 'Preview:' not in str(preview.get('rubric_evaluator', '')):
        errors.append('Preview label for the rubric evaluator is required.')
    if 'Preview:' not in str(preview.get('agent_optimizer', '')):
        errors.append('Preview label for Agent Optimizer is required.')
    metadata = _load_yaml(agent_root / '.foundry' / 'agent-metadata.yaml')
    suite_ids = {suite['id'] for suite in manifest.get('suites', [])}
    metadata_suite_ids = {
        suite['id']
        for suite in metadata.get('environments', {}).get('dev', {}).get('evaluationSuites', [])
        if isinstance(suite, dict) and 'id' in suite
    }
    if metadata_suite_ids != suite_ids:
        errors.append('agent-metadata.yaml evaluationSuites do not match the local suite manifest ids.')
    for suite in metadata.get('environments', {}).get('dev', {}).get('evaluationSuites', []):
        if not isinstance(suite, dict):
            continue
        for field in ('suiteFile', 'datasetFile', 'datasetContentPath'):
            relative_path = suite.get(field)
            if not isinstance(relative_path, str):
                errors.append(f"Evaluation suite {suite.get('id', '<unknown>')} is missing {field}.")
                continue
            if not (agent_root / relative_path).resolve().is_file():
                errors.append(
                    f"Evaluation suite {suite.get('id', '<unknown>')} points to a missing {field}: {relative_path}"
                )
    optimization = manifest.get('optimization', {})
    if optimization.get('candidate_apply') != 'manual_only':
        errors.append('Optimizer candidate_apply must be manual_only.')
    constraints = optimization.get('execution_constraints', {})
    if (
        constraints.get('non_production_data_only') is not True
        or constraints.get('read_only') is not True
    ):
        errors.append(
            'Optimizer execution constraints must stay '
            'non_production_data_only=true and read_only=true.'
        )
    prohibited = set(constraints.get('prohibited_mutations', []))
    if prohibited != {'accounts', 'content', 'email', 'teams'}:
        errors.append('Optimizer prohibited_mutations must be exactly accounts, content, email, and teams.')
    return errors


def gate_suite_result(
    suite_id: str,
    score_card: dict[str, Any],
    manifest: dict[str, Any],
    rubric: dict[str, Any],
) -> GateResult:
    suites = {suite['id']: suite for suite in manifest['suites']}
    suite = suites[suite_id]
    rubric_dimensions = {dimension['id']: dimension for dimension in rubric['dimensions']}
    failures: list[GateFailure] = []
    aggregate = float(score_card['aggregate'])
    if aggregate < float(suite['min_aggregate']):
        failures.append(GateFailure('aggregate_below_minimum', f'{aggregate} < {suite["min_aggregate"]}'))
    previous = score_card.get('previous_aggregate')
    if previous is not None:
        previous_value = float(previous)
        tolerance = float(suite.get('regression_tolerance', 0.0))
        if aggregate + tolerance < previous_value:
            failures.append(GateFailure('aggregate_regression', f'{aggregate} regressed from {previous_value} beyond tolerance {tolerance}'))
        floor = float(suite['regression_floor'])
        if aggregate < floor:
            failures.append(GateFailure('aggregate_below_regression_floor', f'{aggregate} < {floor}'))
    dimensions = score_card.get('dimensions', {})
    if not isinstance(dimensions, dict):
        failures.append(GateFailure('malformed_dimensions', 'score_card.dimensions must be a mapping'))
        return GateResult(False, tuple(failures))
    for dimension_id in suite['hard_gate_dimensions']:
        if dimension_id not in dimensions:
            failures.append(GateFailure('missing_hard_gate_dimension', dimension_id))
            continue
        observed = float(dimensions[dimension_id])
        threshold = float(rubric_dimensions[dimension_id]['threshold'])
        if observed < threshold:
            failures.append(GateFailure('hard_gate_failure', f'{dimension_id}={observed} < {threshold}'))
    return GateResult(not failures, tuple(failures))
