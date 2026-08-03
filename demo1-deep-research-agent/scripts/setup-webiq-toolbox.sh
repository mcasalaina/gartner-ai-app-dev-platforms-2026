#!/usr/bin/env bash
set -euo pipefail

: "${WEBIQ_API_KEY:?Set WEBIQ_API_KEY before creating the connection}"

project_endpoint="$(AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value FOUNDRY_PROJECT_ENDPOINT)"

AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd ai connection create webiq \
  --kind remote-tool \
  --target 'https://api.microsoft.ai/v3/mcp' \
  --auth-type custom-keys \
  --custom-key "x-apikey=$WEBIQ_API_KEY" \
  --project-endpoint "$project_endpoint"

result="$(AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd ai toolbox create \
  webiq-research \
  --from-file src/bank-deep-research/toolbox.yaml \
  --project-endpoint "$project_endpoint" \
  --output json)"

toolbox_endpoint="$(printf '%s' "$result" | jq -r '.endpoint // .mcpEndpoint // empty')"
if [[ -z "$toolbox_endpoint" ]]; then
  printf '%s\n' "$result"
  echo "Toolbox created, but its endpoint could not be parsed." >&2
  exit 1
fi

AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set TOOLBOX_ENDPOINT "$toolbox_endpoint"
echo "Web IQ toolbox configured at $toolbox_endpoint"
