# Demo 1: Foundry Deep Research Agent

A live localhost experience for the Gartner AI Application Development Platforms
2026 evaluation. The system uses a Microsoft Foundry Hosted Agent, parallel
`gpt-5.4-mini` workers grounded only through Microsoft Web IQ,
`gpt-5.4-mini` planning and synthesis, `FLUX-1.1-pro`, Azure Speech, human plan approval,
Application Insights tracing, and cited PDF export.

## Architecture

- **Frontend:** React, Vite, and TypeScript at `http://localhost:5173`
- **Local API:** FastAPI, SQLite checkpoints, SSE, and artifact generation at
  `http://localhost:8000`
- **Primary Foundry project:** West US, with the Hosted Agent,
  `gpt-5.4-mini` and a reserved `model-router` deployment for future demos
- **Supporting AI Services resource:** West US, with `FLUX-1.1-pro`
- **Grounding:** Web IQ MCP behind a Foundry Toolbox
- **Speech:** Passwordless Azure Speech synthesis

No replay or canned-research mode exists. A run without configured live services
fails with an actionable stage error and preserves completed work.

## Prerequisites

- Azure CLI and Azure Developer CLI
- `azd` authenticated to the tenant that owns **M365 Advocacy (new)**,
  subscription `27b0139a-16b4-42bf-9ec9-c6db3768245e`
- Docker and Docker Compose
- A Web IQ API key in `WEBIQ_API_KEY`
- Python 3.13 for host-based backend development
- Node.js 22 or later

## Configure Azure authentication

Authenticate to the M365 Advocacy tenant and select its subscription:

```bash
azd auth login --tenant-id a9d9510e-7131-4355-8b7e-37e7b1e99862
az account set --subscription 27b0139a-16b4-42bf-9ec9-c6db3768245e
```

Then verify:

```bash
az account show --query "{name:name,id:id,tenantId:tenantId}" -o table
azd auth login --check-status
```

## Provision and deploy

The primary Foundry project and its text, research, and future Model Router
deployments are declared in `azure.yaml`. The current demo uses
`gpt-5.4-mini` for all current workers; `model-router` is provisioned but not called.
The router uses balanced routing constrained to `gpt-5.4`, `gpt-5.4-mini`, and
`gpt-5.4-nano`.
The `postprovision` hook deploys the supporting FLUX image model, Speech, and
Storage from `infra/secondary.bicep`. Every resource is in M365 Advocacy (new)
and West US.

```bash
cd demo1-deep-research-agent
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd provision --no-prompt
```

Create the managed Web IQ connection and toolbox without writing the API key to
source or the azd environment:

```bash
export WEBIQ_API_KEY="<key>"
./scripts/setup-webiq-toolbox.sh
```

Deploy the Hosted Agent:

```bash
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd deploy --no-prompt
```

Retrieve the deployed endpoint and supporting outputs:

```bash
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-values
```

Copy the invocations endpoint and generated service outputs into a local `.env`
based on `.env.example`.

## Run on localhost

### Docker Compose

`DefaultAzureCredential` needs a service principal when the backend runs inside
Docker. Export `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, and `AZURE_CLIENT_SECRET`
without saving them to the repository, then run:

```bash
docker-compose up --build
```

### Host development

Host development can reuse the Azure CLI login:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --port 8000
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Validation

```bash
python -m pytest backend/tests
cd frontend && npm run lint && npm run build
docker-compose config
```

For the Hosted Agent itself:

```bash
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd ai agent run --no-client
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd ai agent invoke --local \
  '{"message":"{\"action\":\"plan\",\"run_id\":\"smoke\",\"prompt\":\"Develop a cited global bank strategy for the Gartner scenario.\",\"research_depth\":\"executive\",\"attachment_summaries\":[]}"}'
```

## Security

- Web IQ credentials are held in a Foundry project connection.
- Azure service keys are disabled; local and hosted calls use Microsoft Entra ID.
- The frontend receives no Azure credentials.
- Uploads and generated artifacts stay under ignored local run directories.
- Telemetry excludes authorization headers, API keys, and full uploaded documents.
