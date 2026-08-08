# Azure Deployment Plan

> **Status:** Demo 1 Validated; Demos 2/3 Validated; Demo 4 Deployed

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

## 12. Gartner Demos 2 and 3 — Bank Servicing Agent

### Approved scope

The user approved a new `demo2-3-bank-servicing-agent/` implementation that
combines Demos 2 and 3 as one Python 3.13 Microsoft Foundry hosted agent with
two system-controlled modes.

| Attribute | Value |
|---|---|
| Classification | POC / executive demo |
| Scale | Single presenter; one web-backend replica because voice handles are in memory |
| Subscription | M365 Advocacy (new) (`27b0139a-16b4-42bf-9ec9-c6db3768245e`) |
| Foundry project | `4iq-foundry-project` |
| Foundry endpoint | `https://4iq-foundry-project-resource.services.ai.azure.com/api/projects/4iq-foundry-project` |
| Location | East US 2, inherited from the explicitly selected project |
| Production model | Existing `gpt-5.4-mini` deployment |
| Voice | Voice Live `en-US-Davis:DragonHDLatestNeural` |
| Web access | Public shell; Entra sign-in required for every agent/API/voice action |

### Architecture

| Component | Azure service | Path |
|---|---|---|
| Bank Servicing Agent | Foundry hosted agent, Responses 2.0 | `demo2-3-bank-servicing-agent/src/bank-servicing-agent` |
| Authenticated web API and Voice Live proxy | Azure Container Apps | `demo2-3-bank-servicing-agent/web/backend` |
| Customer/admin web | Azure Container Apps | `demo2-3-bank-servicing-agent/web/frontend` |
| Agent 365 bridge | Azure Container Apps plus Entra Auth SDK sidecar | `demo2-3-bank-servicing-agent/a365/bridge` |
| Reviewed content/media and evaluation artifacts | Private Blob Storage with versioning and soft delete | `demo2-3-bank-servicing-agent/content` |
| Confidential app credential | Key Vault with RBAC and purge protection | `demo2-3-bank-servicing-agent/infra` |
| Telemetry | Existing `4iq-foundry-project-resource-appinsights` | Shared by agent, web, bridge, and evaluations |
| ASSERT | Manual Container Apps Job | `demo2-3-bank-servicing-agent/evaluation/assert` |

The hosted agent reuses the existing Fabric IQ, bank Foundry IQ, Work IQ, model,
and telemetry assets. A separate Demo 1 service knowledge base is created so
the existing policy corpus is not overwritten.

### Identity

- The SPA uses authorization code with PKCE for the web API.
- MSAL uses same-window redirects and tab-scoped `sessionStorage`. Redirect
  processing is incompatible with `memoryStorage`; no popup flow is used.
- The web API validates the user token and performs confidential-client OBO to
  `https://ai.azure.com/.default`.
- Foundry Responses protocol 2.0 supplies trusted user/call identifiers and
  propagates the call ID to user-scoped Toolbox connections.
- Voice Live is opened by the backend with the same OBO user token; the browser
  receives only an opaque, short-lived, one-use handle.
- The replacement Agent 365 bridge preserves the existing standalone
  agent-user identity and calls the same hosted-agent endpoint.
- Production Azure code uses managed identity and resource-scoped RBAC.

### Model and quota plan

- Do not create another `gpt-5.4-mini` deployment; East US 2 usage is 1,198 of
  1,200.
- The admin-only A/B lab uses existing `gpt-5.4-mini`, `gpt-5-mini`, and
  `gpt-4.1-mini` deployments.
- Agent Optimizer requires a separate supported optimization model. East US 2
  has no `gpt-5.4` standard quota, so use GA `DeepSeek-V4-Pro` at the validated
  live capacity of 1. Its deployment is isolated in
  `infra/optimizer-model.bicep` and is not created by the base web deployment.

### Security and data

- No API keys, client secrets, bearer tokens, real customer data, or salary
  content are committed or logged.
- Key Vault references supply the confidential-client credential.
- Blob public access is disabled; versioning, change feed, and delete retention
  are enabled.
- Only synthetic KYC/account-opening data is used.
- Bank-domain, prompt-injection, cross-user, salary-DLP, and confirmation gates
  fail closed before downstream writes.
- Reviewer/admin APIs enforce Entra app roles.

### Execution checklist

- [x] User approved the architecture and source-of-truth folder
- [x] Confirm selected subscription, project, location, model deployments, and quota
- [x] Create the repository and Foundry agent scaffold
- [x] Complete hosted-agent, data, identity, web, bridge, and evaluation code
- [x] Generate and build supporting Bicep
- [x] Complete local functional verification
- [x] Set this document to `Ready for Validation`
- [x] Complete `azure-validate` with final deployment identities, credentials, images, and sidecar
- [x] Invoke `azure-deploy` only after validation succeeds

### Validation steps

- [x] Compile and lint every Bicep template
- [x] Run local agent, backend, bridge, frontend, content, rubric, and ASSERT checks
- [x] Confirm Azure CLI authentication, subscription, tenant, project region, and target resource group
- [x] Run ARM template validation with non-secret structural placeholders
- [x] Run ARM what-if and confirm it contains no deletes or modifications
- [x] Review static RBAC assignments for data-plane access and resource-level scope
- [x] Inspect subscription policy assignments
- [x] Build all production images with Azure Container Registry remote builds
- [x] Substitute and validate final Entra, Agent 365, registry image, and sidecar values

### Validation proof

| Check | Result |
|---|---|
| Local application suites | Agent 22 passed and Ruff passed; backend 23 passed; bridge 4 passed; content/shared-rubric 6 passed; frontend lint, 4 tests, and production build passed; ASSERT configuration, 21 tests, and Ruff passed |
| Foundry assets and Toolbox | Evaluation/optimizer asset validation and Toolbox dry-run passed |
| Bicep | Base infrastructure, ACR role module, optimizer model, and ASSERT job compile; `main.bicep` lint is clean |
| Azure authentication | Authenticated to `M365 Advocacy (new)` (`27b0139a-16b4-42bf-9ec9-c6db3768245e`) in tenant `a9d9510e-7131-4355-8b7e-37e7b1e99862` |
| ARM validation | Final resource-group validation succeeded in `rg-aycabas-3iqs` with the live app IDs, Agent 365 IDs, image references, and credentials; live optimizer deployment succeeded at capacity 1 after quota rejected 5,000 |
| ARM what-if | Succeeded with 21 creates, 0 modifies, and 0 deletes |
| Azure Policy | No subscription policy assignments returned |
| Role assignment verification | Separate frontend, backend, and bridge identities; each has resource-scoped `AcrPull`; backend alone has `Storage Blob Data Contributor`; backend and bridge alone have `Key Vault Secrets User` |
| Model catalog | `DeepSeek-V4-Pro` version `2026-04-23` is available with `GlobalStandard` and `DataZoneStandard`; the optimizer-only live deployment uses capacity 1 |
| Container packaging | ACR remote builds succeeded; the active OBO images are frontend `20260805.2` and backend `20260805.1` in `workmateacr4b5a1.azurecr.io` |
| Entra registrations | Created dedicated API `e0c8999e-b5da-4d80-aef9-65c5bc18435b` and SPA `0946f17c-5ce5-4804-9508-a1d5f66af61f`; configured delegated scope, reviewer/admin roles, preauthorization, Azure AI admin consent, and fresh one-year credentials |
| Agent 365 identity | Matched agent user `a7a91f6a-1c79-43f3-9653-c6a728d64f9c` to Entra agent ID `439176bf-94bd-497f-985b-a3c93cc989b2` by exact creation timestamp; retained blueprint `2c3685f3-7ad7-467b-96e8-dd3d06b99f55` |

### Live OBO deployment proof

| Check | Result |
|---|---|
| Hosted agent | `bank-servicing-agent` version 15 is active on Responses 2.0 with `gpt-5.4-mini` |
| Web OBO | Signed-in service and customer first turns plus same-conversation follow-ups passed through the SPA, API validation, OBO exchange, and hosted agent |
| Guard continuity | Salary DLP, unrelated-domain refusal, and a subsequent valid banking response passed in one conversation without downstream contamination |
| Voice Live | Single-use handle, OBO WebSocket, hosted-agent session, Azure Speech transcript, and Davis audio passed; the spoken smoke test returned 333,600 audio bytes |
| Timeout | Backend uses a configurable 90-second Foundry timeout; live grounded calls up to 38 seconds completed |
| Telemetry | Both modes recorded with `gpt-5.4-mini`; token-hygiene query found zero bearer or JWT-like values |
| Deferred channel | Agent 365 standalone cutover remains separate from the verified OBO baseline |

**Validated by:** `azure-validate` workflow
**Validation completed:** 2026-08-04
**Validation status:** Complete for `M365 Advocacy (new)` in East US 2.

## 13. Gartner Demo 4 — Talking Avatar Validation

Demo 4 extends the existing East US 2 Bank Servicing Agent deployment with the
standard Amara photo avatar, Ava multilingual voice, trusted delivery tones,
WebRTC media, and a read-only `avatar_marketing` mode.

### Validation proof

| Check | Command | Result | Timestamp |
|---|---|---|---|
| Azure authentication | `azd auth login --check-status` | Pass for the existing M365 Advocacy subscription | 2026-08-07 |
| Subscription and region | `az account show`; live resource queries | Pass: `27b0139a-16b4-42bf-9ec9-c6db3768245e`, existing app environment in East US 2 | 2026-08-07 |
| Hosted-agent schema | `azd ai agent doctor --output json` | Local schema, project endpoint, authentication, role, and environment checks pass; the newly recreated local AZD environment has no deployment tracking until this version is deployed | 2026-08-07 |
| Hosted-agent package | `azd package bank-servicing-agent --no-prompt` | Pass | 2026-08-07 |
| Frontend | `npm run typecheck && npm run lint && npm test && npm run build` | Pass: 9 tests and production Vite build | 2026-08-07 |
| Python syntax and guards | `python3 -m compileall`; direct multilingual guard smoke checks | Pass; full pytest dependency restoration is blocked by organizational access policy for `files.pythonhosted.org` | 2026-08-07 |
| Voice Live interim responses | `python3 -m compileall`; production-runtime session payload assertions; `az bicep build` | Pass: static interim responses enable both `tool` and `latency` triggers with an 800ms latency threshold | 2026-08-08 |
| Bicep | `az bicep build --file infra/main.bicep --stdout` | Pass | 2026-08-07 |
| ARM validation | `az deployment group validate` with live non-secret values and structural secure placeholders | Pass | 2026-08-07 |
| ARM what-if | `az deployment group what-if --result-format ResourceIdOnly` | Pass: 21 deploy, 31 ignore, 0 delete | 2026-08-07 |
| Azure Policy | `az policy assignment list` | Pass: no subscription policy assignments | 2026-08-07 |
| Static RBAC | Review of `main.bicep` and `acr-pull-role.bicep` | Pass: resource-scoped Blob Data Contributor, Key Vault Secrets User, and ACR Pull assignments remain unchanged | 2026-08-07 |

**Validated by:** azure-validate workflow. **Validation status:** Demo 4 is
`Validated` for M365 Advocacy (new), East US 2.

### Deployment proof

| Check | Result | Timestamp |
|---|---|---|
| Hosted agent | `bank-servicing-agent` version 34 active on Responses 2.0 | 2026-08-07 |
| Frontend | `bank-servicing-frontend:20260808.3`, revision `bank-servicing-web--0000018`, healthy and receiving 100% traffic | 2026-08-08 |
| Backend | `bank-servicing-backend:20260808.3`, revision `bank-servicing-api--0000014`, healthy and receiving 100% traffic | 2026-08-08 |
| Runtime config | Live probe returned `avatar_marketing`, Amara, `vasa-1`, `en-US-AlloyTurboMultilingualNeural`, avatar enabled, and interim responses enabled for `tool` and `latency` at 800ms | 2026-08-08 |
| Public frontend | HTTP 200 and deployed bundle contains `Talk with Avatar` and `Alloy Multilingual` | 2026-08-07 |
| Authenticated Edge acceptance | Both chat modes returned HTTP 200; avatar delivered 512x512 audio/video through WebRTC; microphone mute, unmute, and cleanup passed; the workspace filled the 1912px Edge viewport with zero horizontal overflow | 2026-08-08 |
| Avatar presentation | Live bundle displays `Meet the Avatar` and `Talk naturally in any language`, with no character name exposed in the interface | 2026-08-08 |
| Live RBAC | Frontend/backend/bridge retain ACR Pull; backend retains Storage Blob Data Contributor and Key Vault Secrets User; bridge retains Key Vault Secrets User | 2026-08-07 |

**Live frontend:** `https://bank-servicing-web.agreeablewave-d7d8bc74.eastus2.azurecontainerapps.io`

**Live API:** `https://bank-servicing-api.agreeablewave-d7d8bc74.eastus2.azurecontainerapps.io`
