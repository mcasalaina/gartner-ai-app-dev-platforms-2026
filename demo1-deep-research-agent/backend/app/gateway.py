import asyncio
import json

import httpx
from azure.core.credentials import TokenCredential
from azure.identity import DefaultAzureCredential

from .models import AgentRequest


class AgentGateway:
    def __init__(
        self,
        endpoint: str | None,
        api_version: str,
        credential: TokenCredential | None = None,
    ):
        self._endpoint = endpoint
        self._api_version = api_version
        self._credential = credential

    async def invoke(self, request: AgentRequest) -> dict:
        if not self._endpoint:
            raise RuntimeError(
                "FOUNDRY_AGENT_ENDPOINT is not configured. Provision and deploy "
                "the hosted agent, then set its invocations endpoint."
            )

        credential = self._credential or DefaultAzureCredential()
        token = await asyncio.to_thread(
            credential.get_token, "https://ai.azure.com/.default"
        )
        async with httpx.AsyncClient(timeout=httpx.Timeout(900.0)) as client:
            response = await client.post(
                self._endpoint,
                params={"api-version": self._api_version},
                headers={
                    "Authorization": f"Bearer {token.token}",
                    "Content-Type": "application/json",
                },
                json={"message": request.model_dump_json()},
            )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            try:
                error = response.json().get("error", {})
            except json.JSONDecodeError:
                error = {}
            code = error.get("code", "unknown_error")
            message = error.get("message", response.reason_phrase)
            raise RuntimeError(
                f"Hosted agent request failed ({response.status_code}, {code}): "
                f"{message}"
            ) from exc
        payload = response.json()
        raw_result = payload.get("response", payload)
        if isinstance(raw_result, str):
            try:
                return json.loads(raw_result)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    "Hosted agent returned a non-JSON response."
                ) from exc
        return raw_result
