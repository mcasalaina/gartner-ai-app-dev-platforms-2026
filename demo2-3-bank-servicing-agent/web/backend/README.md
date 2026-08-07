# Bank Servicing backend

This FastAPI service validates Microsoft Entra user tokens, exchanges them with a confidential-client on-behalf-of flow for `https://ai.azure.com/.default`, and proxies chat and Voice Live traffic to `bank-servicing-agent`.

Voice session handles use an in-memory store behind an interface. That implementation is intentionally short-lived and single-replica only.
