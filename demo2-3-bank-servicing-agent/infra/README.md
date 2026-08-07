# Supporting infrastructure

`main.bicep` deploys the signed-in web frontend, OBO/Voice Live backend,
replacement Agent 365 bridge, managed identity, Key Vault, and versioned private
Blob Storage. It reuses the existing project Log Analytics and Application
Insights resources.

The backend is intentionally fixed at one replica because voice handles are
short-lived and in memory. Replace the handle store with a distributed,
encrypted implementation before increasing replicas.

`optimizer-model.bicep` is deliberately separate. Validate model catalog
availability and East US 2 quota immediately before deploying it; it is not part
of the base web deployment.

No parameter file contains a secret value. Supply the web confidential-client
secret from the deployment environment, and Bicep stores it in Key Vault.

