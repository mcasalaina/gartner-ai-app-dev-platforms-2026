# Bank Servicing Agent ASSERT evaluation

This isolated Python 3.13 project ports the reviewed ASSERT **beta** pattern from
`~/src/hotel-agent-a365` and tailors it to the Bank Servicing Agent.

- It evaluates the deployed Bank Servicing Agent through a real Microsoft Entra
  Agent ID **user** token acquired from a loopback-only Entra Auth SDK sidecar.
- It never falls back to a developer token, API key, managed identity, or
  `x-ms-user-identity` header as the target identity.
- ASSERT stays isolated from the production hosted-agent and web dependencies.

## Install

```bash
python3.13 -m venv demo2-3-bank-servicing-agent/evaluation/assert/.venv
demo2-3-bank-servicing-agent/evaluation/assert/.venv/bin/python   demo2-3-bank-servicing-agent/evaluation/assert/scripts/bootstrap_assert.py --install
demo2-3-bank-servicing-agent/evaluation/assert/.venv/bin/python   demo2-3-bank-servicing-agent/evaluation/assert/scripts/run_assert_evaluation.py validate
```

The bootstrap script clones the reviewed ASSERT commit, builds it with fixed
build inputs, verifies the wheel SHA-256 in `assert-source.lock.json`, and
installs the wheel plus this project into the active environment.

## Live identity configuration

Run the Entra Auth SDK sidecar in the same pod or host trust boundary and expose
it only on loopback. Configure its `Foundry` downstream API with scope
`https://ai.azure.com/.default`. The target requires these environment values:

```text
ASSERT_TENANT_ID
ASSERT_FOUNDRY_AUDIENCE
ASSERT_AGENT_USER_ID
ASSERT_AGENT_IDENTITY_ID
ASSERT_PARENT_BLUEPRINT_ID
ASSERT_SIDECAR_URL=http://127.0.0.1:5000
ASSERT_SIDECAR_SERVICE=Foundry
AZURE_AI_FOUNDRY_ENDPOINT
FOUNDRY_AGENT_NAME=bank-servicing-agent
FOUNDRY_AGENT_VERSION=6
FOUNDRY_MODEL_NAME
```

Any mismatch in signature, lifetime, tenant, audience, `idtyp=user`,
agent-user facet `13`, agent-identity facet `11`, or parent blueprint fails the
run before the Bank Servicing Agent is invoked.

## Reviewed suites

- `config/smoke.yaml` loads 12 reviewed smoke cases: 8 fixed prompts and 4
  adaptive two-turn scenarios covering service follow-ups, customer
  corrections, mode changes, KYC confirmation, salary probes, cross-user
  leakage, prompt injection, and unsupported non-bank requests.
- `config/regression.yaml` generates broader synthetic coverage conversations.
- `config/adversarial.yaml` generates hostile safety scenarios.

`live` performs the no-content Work IQ preflight, runs ASSERT with inference
concurrency one, imports correlated Application Insights spans, judges OTLP
trace groups by `session.id`, and applies the Bank Servicing Rubric gates. It
fails if any reviewed case is unjudged, any hard-gate dimension fails, trace
correlation is incomplete, or the shared banking rubric score is below `0.90`.

## Results viewer

The local viewer comes from the same pinned ASSERT source:

```bash
python3 demo2-3-bank-servicing-agent/evaluation/assert/scripts/run_assert_ui.py
```

It binds to `http://127.0.0.1:5174`, reads the ignored
`evaluation/assert/artifacts/results/` directory, and starts in read-only mode.
Do not commit raw transcripts or traces.

Legacy runs can be upgraded once without rerunning inference or judging. The
migration preserves the original transcript and score files under
`.legacy-viewer-schema/`; rebuild the standard viewer's derived read model
afterward:

```bash
RUN_DIR=demo2-3-bank-servicing-agent/evaluation/assert/artifacts/results/bank-servicing-conversations/20260805T054917Z
python3 demo2-3-bank-servicing-agent/evaluation/assert/scripts/migrate_legacy_viewer_artifacts.py "$RUN_DIR"
PYTHONPATH=demo2-3-bank-servicing-agent/evaluation/assert/.runtime/source \
  demo2-3-bank-servicing-agent/evaluation/assert/.venv/bin/python -c \
  'import sys; from pathlib import Path; from assert_ai.viewer_read_model import build_run_viewer_artifacts; build_run_viewer_artifacts(Path(sys.argv[1]))' \
  "$RUN_DIR"
```

## Controlled execution artifacts

- `automation/assert-job.bicep` defines a manually triggered Container Apps Job
  pattern tailored to the Bank Servicing Agent.
- `automation/assert-evaluation.workflow.yml` mirrors the hotel repo's
  GitHub OIDC start-job workflow as a local artifact only.

These artifacts are documentation and templates inside `evaluation/assert`; they
are not live infrastructure changes.
