# Bank Servicing Agent

Gartner Demos 2 through 4 use one Microsoft Foundry hosted agent in three
system-controlled modes:

- **Service discovery:** cited service information and images, generated service
  media, Voice Live, deterministic quality control, editorial review, and
  feedback.
- **Customer servicing:** account opening and KYC guidance, account
  and investment servicing, PDF-grounded RAG, bank guardrails, salary DLP, and
  quality/cost reporting.
- **Avatar marketing:** read-only, multilingual service explanations through the
  standard Amara photo avatar and Alloy multilingual voice, with safe navigation
  between the two existing banking workspaces.

The web shell is public, but every API and voice session requires Microsoft
Entra sign-in. The Agent 365 bridge uses the same hosted agent with its existing
standalone agent-user identity.

The deployed OBO path uses same-window MSAL redirects with tab-scoped
`sessionStorage`, a 90-second bounded Foundry request timeout, and opaque
single-use Voice Live handles. The Voice Live proxy targets the Responses
hosted-agent contract with API version `2026-04-10` and query parameters
`agent-name` and `agent-project-name`; the classic `agent_id` and `project_id`
parameters are not used. It translates browser PCM to Voice Live events and
relays avatar WebRTC signaling without exposing the OBO token.

## Components

| Path | Purpose |
|---|---|
| `src/bank-servicing-agent` | Python 3.13 Responses 2.0 hosted agent |
| `web/backend` | Authenticated FastAPI/OBO and Voice Live proxy |
| `web/frontend` | React customer and administration experience |
| `a365/bridge` | Agent 365 to Foundry Responses adapter |
| `content` | Demo 1 corpus and service publishing contracts |
| `evaluation/assert` | Pinned ASSERT response-and-trace evaluation |
| `infra` | Supporting web, identity, storage, and evaluation resources |

## Foundry target

- Project: `4iq-foundry-project`
- Endpoint:
  `https://4iq-foundry-project-resource.services.ai.azure.com/api/projects/4iq-foundry-project`
- Production model: `gpt-5.4-mini`
- Avatar: standard Amara photo avatar on `vasa-1`
- Voice: `en-US-AlloyTurboMultilingualNeural`
- Avatar region: East US 2
- Active hosted-agent version: `34`
- Live frontend image: `bank-servicing-frontend:20260808.2`
- Live backend image: `bank-servicing-backend:20260807.3`
- Live Agent 365 bridge image: `marcos-teller-bridge-a365:20260805.8`
- Live Agent 365 bridge revision: `marcos-teller-bridge-a365--0000019`

Existing Fabric IQ, Foundry IQ, Work IQ, model, and telemetry assets are reused.
The existing prompt agent remains available for rollback while the Agent 365
bridge is cut over.

Demo 3 uses the preserved **Marco's Teller** standalone Agent 365 identity and its
existing Teams and mailbox presence. Customer fee-dispute email is triaged with
the agent-user identity, not the presenter's OBO identity. The bridge creates a
threaded agent-owned Graph reply, honors an explicitly requested allowlisted Cc,
applies the General label, and requires employee confirmation before any account
change. It has no fee-write capability.

## Local workflow

Copy `.env.example` to `.env`, fill only local settings, and authenticate with
Azure CLI. Production uses managed identity and Key Vault.

```bash
azd ai agent run
azd ai agent invoke --local "Show me our banking services"
```

Run the web backend and frontend from their component folders. Evaluation
artifacts are ignored and must not contain raw credentials or real customer
data.

## Preview disclosure

The native Foundry bank-servicing rubric is the primary quality evaluator.
Foundry rubric evaluators and Agent Optimizer are preview capabilities, and
ASSERT is beta. Deterministic hard gates and selected built-in evaluators remain
independent secondary evidence.

Presenter sequence and rollback steps are in
[`docs/presenter-runbook.md`](docs/presenter-runbook.md).
The recording-oriented flow, portal proof points, and slide recommendations are
in [`docs/Gartner-Demos-2-and-3-Presenter-Flow.docx`](docs/Gartner-Demos-2-and-3-Presenter-Flow.docx).
