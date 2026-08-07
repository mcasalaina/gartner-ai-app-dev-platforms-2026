from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager, AsyncExitStack
from dataclasses import dataclass
from typing import Any

import httpx
from agent_framework import Agent, AgentResponse, FunctionTool, MCPStreamableHTTPTool
from agent_framework.foundry import FoundryChatClient
from azure.core.exceptions import ClientAuthenticationError

from bank_servicing_agent.agent_context import current_platform_user_id

WORK_IQ_SCOPE = "Tools.ListInvoke.All"
TOKEN_EXCHANGE_SCOPE = "api://AzureADTokenExchange/.default"
KEY_VAULT_SCOPE = "https://vault.azure.net/.default"
CLIENT_ASSERTION_TYPE = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"

WORK_IQ_MAIL_READ_TOOLS = (
    "GetMessage",
    "SearchMessages",
    "SearchMessagesQueryParameters",
    "GetAttachments",
    "DownloadAttachment",
    "mcp_MailTools_graph_mail_getMessage",
    "mcp_MailTools_graph_mail_searchMessages",
)
WORK_IQ_MAIL_SEND_TOOLS = (
    "SendEmailWithAttachments",
    "SendMail",
    "mcp_MailTools_graph_mail_sendMail",
)

HttpClientFactory = Callable[[], AbstractAsyncContextManager[httpx.AsyncClient]]
WorkIQQueryRunner = Callable[
    [str, str, Any, "WorkIQMailServer", str, str, bool],
    Awaitable[str],
]


@dataclass(frozen=True, slots=True)
class WorkIQMailServer:
    url: str
    audience: str

    @property
    def scope(self) -> str:
        return f"{self.audience}/{WORK_IQ_SCOPE}"


class WorkIQAuthenticationUnavailableError(RuntimeError):
    pass


class AgenticUserTokenProvider:
    def __init__(
        self,
        *,
        tenant_id: str,
        blueprint_client_id: str,
        instance_client_id: str,
        blueprint_secret_vault_url: str,
        blueprint_secret_name: str,
        credential: Any,
        http_client_factory: HttpClientFactory | None = None,
    ) -> None:
        self._tenant_id = tenant_id
        self._blueprint_client_id = blueprint_client_id
        self._instance_client_id = instance_client_id
        self._blueprint_secret_vault_url = blueprint_secret_vault_url.rstrip("/")
        self._blueprint_secret_name = blueprint_secret_name
        self._blueprint_secret: str | None = None
        self._credential = credential
        self._http_client_factory = http_client_factory or (
            lambda: httpx.AsyncClient(timeout=30, trust_env=False)
        )

    async def get_token(self, agent_user_id: str, scope: str) -> str:
        async with self._http_client_factory() as client:
            blueprint_secret = await self._get_blueprint_secret(client)
            blueprint_token = await self._exchange(
                client,
                "blueprint",
                {
                    "client_id": self._blueprint_client_id,
                    "scope": TOKEN_EXCHANGE_SCOPE,
                    "grant_type": "client_credentials",
                    "client_secret": blueprint_secret,
                    "fmi_path": self._instance_client_id,
                },
            )
            instance_token = await self._exchange(
                client,
                "instance",
                {
                    "client_id": self._instance_client_id,
                    "scope": TOKEN_EXCHANGE_SCOPE,
                    "grant_type": "client_credentials",
                    "client_assertion_type": CLIENT_ASSERTION_TYPE,
                    "client_assertion": blueprint_token,
                },
            )
            return await self._exchange(
                client,
                "delegated user",
                {
                    "client_id": self._instance_client_id,
                    "scope": scope,
                    "grant_type": "user_fic",
                    "client_assertion_type": CLIENT_ASSERTION_TYPE,
                    "client_assertion": blueprint_token,
                    "user_federated_identity_credential": instance_token,
                    "user_id": agent_user_id,
                },
            )

    async def _get_blueprint_secret(self, client: httpx.AsyncClient) -> str:
        if self._blueprint_secret:
            return self._blueprint_secret
        try:
            access_token = await asyncio.to_thread(
                self._credential.get_token,
                KEY_VAULT_SCOPE,
            )
        except ClientAuthenticationError as exc:
            raise WorkIQAuthenticationUnavailableError(
                "Hosted agent identity could not authenticate to Key Vault"
            ) from exc
        try:
            response = await client.get(
                f"{self._blueprint_secret_vault_url}/secrets/{self._blueprint_secret_name}",
                params={"api-version": "7.5"},
                headers={"Authorization": f"Bearer {access_token.token}"},
            )
        except httpx.HTTPError as exc:
            raise WorkIQAuthenticationUnavailableError(
                "Agent 365 blueprint credential retrieval failed"
            ) from exc
        body = _json_object(response, "Key Vault")
        secret = body.get("value")
        if not response.is_success or not secret:
            raise WorkIQAuthenticationUnavailableError(
                "Agent 365 blueprint credential retrieval was rejected"
            )
        self._blueprint_secret = str(secret)
        return self._blueprint_secret

    async def _exchange(
        self,
        client: httpx.AsyncClient,
        stage: str,
        data: dict[str, str],
    ) -> str:
        try:
            response = await client.post(
                f"https://login.microsoftonline.com/{self._tenant_id}/oauth2/v2.0/token",
                data=data,
            )
        except httpx.HTTPError as exc:
            raise WorkIQAuthenticationUnavailableError(
                f"Agent 365 {stage} token exchange request failed"
            ) from exc
        body = _json_object(response, f"Agent 365 {stage} token exchange")
        token = body.get("access_token")
        if response.is_success and token:
            return str(token)
        error = body.get("error", "unknown_error")
        raise WorkIQAuthenticationUnavailableError(
            f"Agent 365 {stage} token exchange failed: {error}"
        )


class WorkIQMailTool:
    def __init__(
        self,
        *,
        project_endpoint: str,
        model_deployment: str,
        credential: Any,
        expected_agent_user_id: str,
        token_provider: AgenticUserTokenProvider,
        server: WorkIQMailServer,
        query_runner: WorkIQQueryRunner | None = None,
    ) -> None:
        self._project_endpoint = project_endpoint
        self._model_deployment = model_deployment
        self._credential = credential
        self._expected_agent_user_id = expected_agent_user_id.casefold()
        self._token_provider = token_provider
        self._server = server
        self._query_runner = query_runner or _query_work_iq_mail

    def as_read_tool(self) -> FunctionTool:
        return FunctionTool(
            name="read_agent_mailbox",
            description=(
                "Read Marco's Teller's own mailbox through Work IQ. Use only in the "
                "Agent 365 channel and only when the user asks about the agent's mailbox."
            ),
            func=self.read_mailbox,
        )

    def as_send_tool(self) -> FunctionTool:
        return FunctionTool(
            name="send_agent_email",
            description=(
                "Send exactly one email from Marco's Teller's mailbox through Work IQ. "
                "Use only in Agent 365 after an explicit user request with exact recipients, "
                "subject, and body. Never retry an unconfirmed send."
            ),
            func=self.send_email,
        )

    async def read_mailbox(self, question: str) -> str:
        resolved_question = question.strip()
        if not resolved_question:
            raise ValueError("question must not be empty")
        return await self._query(
            "Read my own mailbox and answer this request using mailbox evidence only:\n"
            f"{resolved_question}\n"
            "Do not create, update, reply to, or send any message.",
            require_send=False,
        )

    async def send_email(
        self,
        recipient_emails: str,
        subject: str,
        body: str,
        cc_emails: str = "",
    ) -> str:
        recipients = recipient_emails.strip()
        cc_recipients = cc_emails.strip()
        resolved_subject = subject.strip()
        resolved_body = body.strip()
        if not recipients:
            raise ValueError("recipient_emails must not be empty")
        if not resolved_subject:
            raise ValueError("subject must not be empty")
        if not resolved_body:
            raise ValueError("body must not be empty")
        return await self._query(
            "Send exactly one new email now using SendEmailWithAttachments with no "
            "attachments. Do not create a draft and do not retry the tool call.\n"
            f"To recipients: {recipients}\n"
            f"Cc recipients: {cc_recipients or 'none'}\n"
            "Do not add any Bcc recipients.\n"
            f"Subject: {resolved_subject}\n"
            f"Exact body:\n{resolved_body}\n"
            "Report success only after the mail tool confirms the send. If the outcome "
            "is ambiguous, report it as unconfirmed.",
            require_send=True,
        )

    async def _query(self, question: str, *, require_send: bool) -> str:
        user_id = current_platform_user_id()
        if user_id.casefold() != self._expected_agent_user_id:
            raise WorkIQAuthenticationUnavailableError(
                "Agent mailbox tools require the configured Agent 365 user context"
            )
        token = await self._token_provider.get_token(user_id, self._server.scope)
        return await self._query_runner(
            self._project_endpoint,
            self._model_deployment,
            self._credential,
            self._server,
            token,
            question,
            require_send,
        )


async def _query_work_iq_mail(
    project_endpoint: str,
    model_deployment: str,
    credential: Any,
    server: WorkIQMailServer,
    token: str,
    question: str,
    require_send: bool,
) -> str:
    allowed_tools = (
        WORK_IQ_MAIL_SEND_TOOLS if require_send else WORK_IQ_MAIL_READ_TOOLS
    )
    async with AsyncExitStack() as stack:
        client = await stack.enter_async_context(
            httpx.AsyncClient(
                headers={"Authorization": f"Bearer {token}"},
                timeout=120,
                trust_env=False,
            )
        )
        mcp_tool = MCPStreamableHTTPTool(
            name="work-iq-mail",
            url=server.url,
            http_client=client,
            description="Governed Microsoft 365 mailbox tools for Marco's Teller",
            allowed_tools=allowed_tools,
        )
        specialist = Agent(
            client=FoundryChatClient(
                project_endpoint=project_endpoint,
                model=model_deployment,
                credential=credential,
            ),
            name="bank-mail-specialist",
            instructions=(
                "You are Marco's Teller operating only in your own Microsoft 365 "
                "mailbox. Follow the request exactly. For reads, use a read-only mail "
                "tool. For sends, make exactly one SendEmailWithAttachments call and "
                "never retry. Do not claim success unless the mail tool succeeds."
            ),
            default_options={"store": False},
            tools=[mcp_tool],
        )
        await stack.enter_async_context(specialist)
        response = await specialist.run(question)
    successful_calls = _successful_tool_calls(response)
    if require_send:
        send_calls = [
            name
            for name in successful_calls
            if any(candidate.casefold() in name.casefold() for candidate in WORK_IQ_MAIL_SEND_TOOLS)
        ]
        if len(send_calls) != 1:
            raise RuntimeError(
                "Work IQ did not confirm exactly one successful email send"
            )
    elif not successful_calls:
        raise RuntimeError("Work IQ returned no successful mailbox evidence")
    answer = response.text.strip()
    if not answer:
        raise RuntimeError("Work IQ returned no answer")
    return answer


def _successful_tool_calls(response: AgentResponse) -> tuple[str, ...]:
    calls: dict[str, str] = {}
    for message in response.messages:
        for content in message.contents:
            if content.type == "function_call" and content.call_id and content.name:
                calls[content.call_id] = content.name
    successful: list[str] = []
    for message in response.messages:
        for content in message.contents:
            if content.type != "function_result" or not content.call_id:
                continue
            name = calls.get(content.call_id)
            if not name or content.exception or not _has_result(content.result):
                continue
            successful.append(name)
    return tuple(successful)


def _has_result(result: Any) -> bool:
    if result is None:
        return False
    if isinstance(result, str):
        return bool(result.strip())
    if isinstance(result, (list, tuple, dict, set)):
        return bool(result)
    return True


def _json_object(response: httpx.Response, source: str) -> dict[str, Any]:
    try:
        body = response.json()
    except json.JSONDecodeError as exc:
        raise WorkIQAuthenticationUnavailableError(
            f"{source} returned invalid JSON"
        ) from exc
    if not isinstance(body, dict):
        raise WorkIQAuthenticationUnavailableError(
            f"{source} returned an invalid response"
        )
    return body
