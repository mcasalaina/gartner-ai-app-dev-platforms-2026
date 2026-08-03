#!/usr/bin/env bash
set -euo pipefail

: "${AZURE_SUBSCRIPTION_ID:?AZURE_SUBSCRIPTION_ID is required}"
: "${AZURE_RESOURCE_GROUP:?AZURE_RESOURCE_GROUP is required}"
: "${AZURE_AI_ACCOUNT_NAME:?AZURE_AI_ACCOUNT_NAME is required}"

az account set --subscription "$AZURE_SUBSCRIPTION_ID"
principal_id="$(az ad signed-in-user show --query id -o tsv)"
base_name="${AZURE_ENV_NAME:-gartner-bank-research}"

outputs="$(az deployment group create \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --name secondary-ai-services \
  --template-file infra/secondary.bicep \
  --parameters \
    baseName="$base_name" \
    principalId="$principal_id" \
    foundryAccountName="$AZURE_AI_ACCOUNT_NAME" \
  --query properties.outputs \
  --output json)"

image_endpoint="$(printf '%s' "$outputs" | jq -r '.imageModelEndpoint.value')"
image_deployment="$(printf '%s' "$outputs" | jq -r '.imageModelDeployment.value')"
speech_region="$(printf '%s' "$outputs" | jq -r '.speechRegion.value')"
speech_endpoint="$(printf '%s' "$outputs" | jq -r '.speechEndpoint.value')"
speech_resource_id="$(printf '%s' "$outputs" | jq -r '.speechResourceId.value')"
storage_account="$(printf '%s' "$outputs" | jq -r '.storageAccountName.value')"
application_insights_connection_string="$(
  printf '%s' "$outputs" | jq -r '.applicationInsightsConnectionString.value'
)"

AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set \
  IMAGE_MODEL_ENDPOINT "$image_endpoint"
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set \
  IMAGE_MODEL_DEPLOYMENT "$image_deployment"
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set \
  SPEECH_REGION "$speech_region"
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set \
  SPEECH_ENDPOINT "$speech_endpoint"
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set \
  SPEECH_RESOURCE_ID "$speech_resource_id"
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set \
  AZURE_STORAGE_ACCOUNT "$storage_account"
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set \
  APPLICATIONINSIGHTS_CONNECTION_STRING "$application_insights_connection_string"
