# Azure Deployment Plan

> **Status:** Validated

Generated: 2026-08-01

## 1. Project Overview

**Goal:** Build and deploy the complete Gartner Demo 1 deep research experience
with a localhost React/FastAPI interface and Microsoft Foundry Hosted Agent.

**Path:** New project in a new `demo1-deep-research-agent/` directory.

## 2. Requirements

| Attribute | Value |
|-----------|-------|
| Classification | POC / executive demo |
| Scale | Small, single presenter with bounded parallel workers |
| Budget | Balanced; consumption SKUs and minimal model capacity |
| Subscription | M365 Advocacy (new) (`27b0139a-16b4-42bf-9ec9-c6db3768245e`) |
| Primary location | West US |
| Image-model location | West US |
| Data residency | No geographic restriction; user approved deployment wherever capacity exists |
| Local runtime | Docker CLI 29.7.1, Docker Compose 5.3.1, Colima |

No subscription policy assignments constrain this deployment.

## 3. Components

| Component | Type | Technology | Path |
|-----------|------|------------|------|
| web | SPA frontend | React, Vite, TypeScript | `demo1-deep-research-agent/frontend` |
| api | Local API | FastAPI, Python | `demo1-deep-research-agent/backend` |
| bank-deep-research | Hosted agent | Python 3.13, Agent Framework, invocations protocol | `demo1-deep-research-agent/src/bank-deep-research` |
| local orchestration | Container composition | Docker Compose | `demo1-deep-research-agent/docker-compose.yml` |

The repository had no existing application, `azure.yaml`, infrastructure, or
Dockerfiles before this work.

## 4. Recipe Selection

**Selected:** Azure Developer CLI with Bicep.

The Foundry hosted-agent sample owns the primary project and model lifecycle
through `azure.yaml`. A Bicep module adds a supporting West US AI Services
resource for FLUX and the Speech and Storage resources.

## 5. Architecture

**Stack:** Local containers plus Microsoft Foundry Hosted Agent Service.

| Component | Azure service | SKU / configuration |
|-----------|---------------|---------------------|
| Hosted agent and primary project | Microsoft Foundry, West US | Basic Hosted Agent setup |
| Planning, research, and synthesis | Two `gpt-5.4-mini` deployments | GlobalStandard, version `2026-03-17`, capacity 100 each; fixed two-lane research assignment prevents burst throttling while preserving parallel research |
| Future model routing | `model-router` deployment | GlobalStandard, version `2025-11-18`, capacity 10; balanced subset of `gpt-5.4`, `gpt-5.4-mini`, and `gpt-5.4-nano`; provisioned but unused by Demo 1 |
| Generated visuals | Supporting AI Services account, West US | `FLUX-1.1-pro`, GlobalStandard, version `1`, capacity 1 |
| Web grounding | Foundry Toolbox | Web IQ MCP with static-key connection placeholder |
| Narration | Azure Speech | Standard S0 with Entra-authenticated REST synthesis; no native Speech SDK process dependency |
| Artifacts | Blob Storage | Standard_LRS, hot tier |
| Hosted agent package | Foundry code deployment | Python 3.13 remote build; no ACR required |
| Telemetry | Application Insights and Log Analytics | Consumption / PerGB2018 |

The local browser never receives Azure or Web IQ credentials. Local Azure access
uses `DefaultAzureCredential`; hosted access uses managed identity and project
connections. Secrets are excluded from source, logs, prompts, Docker images,
`azure.yaml`, and telemetry.

## 6. Provisioning Limit Checklist

| Resource or quota | Deploy | Current | Limit | Result and source |
|-------------------|--------|---------|-------|-------------------|
| `OpenAI.GlobalStandard.gpt-5.4-mini`, West US | 200 | 998 | 1,200 | Pass; 202 available before deployment, leaving 2 |
| `OpenAI.GlobalStandard.ModelRouter`, West US | 10 | 0 | 10 | Pass; 10 available |
| `AIServices.GlobalStandard.FLUX-1.1-pro`, West US | 1 | 0 | 20 | Pass; 20 available |
| Cognitive Services accounts | 2 | 0 in selected regions | 200 per subscription/region | Pass; Resource Graph plus service limits |
| Storage accounts | 1 | 0 in selected regions | 250 per region | Pass; Resource Graph plus service limits |
| Log Analytics workspaces | 1 | 0 in selected regions | 1,000 per subscription/region | Pass; Resource Graph plus service limits |
| Application Insights components | 1 | 0 in selected regions | No relevant blocking quota at this scale | Pass; Resource Graph |

**Status:** All planned resources and model deployments are within available
M365 Advocacy (new) limits. `az quota` does not support Cognitive Services
scopes, so model quota was validated with Azure Cognitive Services usage and
regional model-capacity APIs.

## 7. Execution Checklist

### Planning

- [x] Analyze workspace
- [x] Gather requirements
- [x] Confirm subscription and location intent
- [x] Scan codebase
- [x] Select recipe
- [x] Plan architecture
- [x] Validate model catalog and quota
- [x] User approved deployment wherever compatible capacity exists

### Preparation

- [x] Install and start Docker-compatible local runtime
- [x] Scaffold Foundry Hosted Agent
- [x] Generate local frontend and backend
- [x] Add secondary model and supporting infrastructure
- [x] Add Dockerfiles and Docker Compose
- [x] Add Web IQ, Speech, telemetry, and evaluation configuration
- [x] Run local functional verification
- [x] Set status to `Ready for Validation`

### Validation and Deployment

- [x] Invoke `azure-validate`
- [x] AZD installation
- [x] `azure.yaml` schema and Hosted Agent manifest validation
- [x] AZD environment setup
- [x] Authentication check for the target subscription
- [x] Subscription and location values
- [x] Provision preview
- [x] Frontend and backend build verification
- [x] Docker build context and Compose validation
- [x] Hosted Agent package validation
- [x] Azure Policy validation
- [x] Static RBAC verification
- [x] Record validation proof
- [x] Invoke `azure-deploy`
- [x] Provision Foundry project, models, Speech, Storage, and supporting services
- [x] Verify Model Router deployment and constrained routing subset
- [x] Create Web IQ connection and Toolbox
- [x] Deploy and verify Hosted Agent

## 8. Validation Proof

| Check | Command | Result | Timestamp |
|-------|---------|--------|-----------|
| AZD installation | `azd version` | Pass: 1.28.0 | 2026-08-01 |
| Foundry manifest | `azd ai agent doctor --output json` | Pass: 11 checks, 0 failures, including remote project and Hosted Agent checks | 2026-08-01 |
| Python tests | `PYTHONPATH=backend .venv/bin/pytest -q backend/tests` | Pass: 2 tests | 2026-08-01 |
| Python compile | `python -m py_compile backend/app/*.py src/bank-deep-research/main.py` | Pass | 2026-08-01 |
| Frontend lint | `npm run lint` | Pass | 2026-08-01 |
| Frontend build | `npm run build` | Pass: 1,938 modules | 2026-08-01 |
| Bicep build | `az bicep build --file infra/secondary.bicep --stdout` | Pass | 2026-08-01 |
| Supporting template validation | `az deployment group validate` | Pass after adding Log Analytics and Application Insights | 2026-08-01 |
| Supporting what-if | `az deployment group what-if` | Pass: creates Log Analytics and Application Insights; existing resources retained | 2026-08-01 |
| Model catalog | `az cognitiveservices model list` | Pass: all selected versions and SKUs available in West US | 2026-08-01 |
| Model quota | `az cognitiveservices usage list` | Pass: `gpt-5.4-mini` usage 1,098 of 1,200; second capacity-100 deployment fits with 2 units remaining | 2026-08-01 |
| Model Router subset | `az bicep build` with `properties.routing` | Pass: balanced routing constrained to the three GPT-5.4 variants | 2026-08-01 |
| Compose schema | `docker-compose config --quiet` | Pass | 2026-08-01 |
| Container build | `docker-compose up -d --build` | Pass | 2026-08-01 |
| Runtime health | `curl http://localhost:8000/health` and `curl http://localhost:5173` | Pass; both containers healthy | 2026-08-01 |
| Browser interaction | Create a live run without cloud config | Pass: stage-specific failure preserved and displayed | 2026-08-01 |
| Azure Policy | `az policy assignment list --scope /subscriptions/27b0139a...` | Pass: no assignments | 2026-08-01 |
| Provision preview | `azd provision --preview --no-prompt` | Pass: creates `gpt-5.4-mini-research`; retains the existing project, models, and supporting resources | 2026-08-01 |
| Agent package | `azd package bank-deep-research --no-prompt` | Pass: fixed two-lane Hosted Agent ZIP generated | 2026-08-01 |
| Hosted Agent research probe | Direct one-section invocation against version 2 | Pass: HTTP 200 with a 17,822-character research result | 2026-08-01 |
| Speech REST synthesis | Entra token plus West US text-to-speech REST endpoint | Pass: generated 206,444-byte PCM WAV without native SDK | 2026-08-01 |

### Role Assignment Verification

- **Status:** Verified statically.
- **Local developer identity:** Cognitive Services User scoped separately to the
  West US image account and West US Speech account.
- **Foundry Hosted Agent identity:** Managed by the `microsoft.foundry` provider
  for its primary project and model deployments.
- **Storage:** No application data-plane operations currently use the provisioned
  account, so no storage role is granted.
- **Scope:** All explicit role assignments are resource-scoped, not subscription
  or resource-group scoped.

**Validated by:** azure-validate workflow  
**Validation status:** Complete. The plan is `Validated` for M365 Advocacy
(new), West US.

## 9. Files to Generate

| File | Purpose | Status |
|------|---------|--------|
| `.azure/deployment-plan.md` | Deployment source of truth | Complete |
| `demo1-deep-research-agent/azure.yaml` | Foundry and hosted-agent lifecycle | Complete |
| `demo1-deep-research-agent/infra/` | Secondary model and supporting resources | Complete |
| `demo1-deep-research-agent/frontend/` | React/Vite application | Complete |
| `demo1-deep-research-agent/backend/` | FastAPI application | Complete |
| `demo1-deep-research-agent/src/bank-deep-research/` | Hosted agent | Complete |
| `demo1-deep-research-agent/docker-compose.yml` | Local composition | Complete |

## 10. Deployment Proof

| Check | Result | Timestamp |
|-------|--------|-----------|
| Subscription | M365 Advocacy (new), `27b0139a-16b4-42bf-9ec9-c6db3768245e` | 2026-08-01 |
| Resource group | `rg-gartner-bank-research-6b7323-00a77604`, West US | 2026-08-01 |
| Foundry project | Provisioned at `https://cog-svwzimd7mmfvc.services.ai.azure.com/api/projects/gartner-bank-research-6b7323` | 2026-08-01 |
| `gpt-5.4-mini` | Succeeded, GlobalStandard capacity 100 | 2026-08-01 |
| Model Router | Succeeded, GlobalStandard capacity 10, balanced mode | 2026-08-01 |
| Router subset | Exactly `gpt-5.4`, `gpt-5.4-mini`, and `gpt-5.4-nano` | 2026-08-01 |
| Router smoke test | Pass: returned `ROUTER_OK`; selected `gpt-5.4-mini-2026-03-17` | 2026-08-01 |
| FLUX | `FLUX-1.1-pro` succeeded, GlobalStandard capacity 1 | 2026-08-01 |
| Speech | Succeeded with local authentication disabled | 2026-08-01 |
| Storage | `dragartnerbankresearch6b` provisioned | 2026-08-01 |

### Live Role Verification

- Cognitive Services User is present on the FLUX resource for the local
  developer identity.
- Cognitive Services User is present on the Speech resource for the local
  developer identity.
- Both application-added roles use resource scope.

## 11. Next Step

Place the `.env` containing `WEBIQ_API_KEY` in this worktree or export the value
to the deployment shell. The only `.env` currently present is azd's generated
environment file, and it does not contain the key. Then create the Web IQ
connection and Toolbox, deploy the Hosted Agent, and run the full live workflow.
