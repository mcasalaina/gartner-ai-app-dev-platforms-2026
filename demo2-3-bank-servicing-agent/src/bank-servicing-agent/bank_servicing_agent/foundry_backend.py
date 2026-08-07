from __future__ import annotations

from agent_framework import Agent, AgentResponse, Content
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import FoundryToolbox

from bank_servicing_agent.config import Settings
from bank_servicing_agent.credentials import select_azure_credential
from bank_servicing_agent.models import GenerationResult
from bank_servicing_agent.work_iq_mail import (
    AgenticUserTokenProvider,
    WorkIQMailServer,
    WorkIQMailTool,
)


_TOOL_SOURCE_ALIASES = (
    ("Fabric IQ", ("fabric-iq-acmebank___", "dataagent_acmebankservicingagent")),
    ("Foundry IQ", ("bank-policy-foundryiq___", "knowledge_base_retrieve")),
    ("Work IQ", ("workiq___", "read_agent_mailbox", "send_agent_email")),
)

class FoundryGenerationBackend:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._credential = select_azure_credential()
        self._client = FoundryChatClient(
            project_endpoint=settings.project_endpoint,
            model=settings.model_deployment,
            credential=self._credential,
        )
        self._agent_mail = self._create_agent_mail_tool(settings)

    async def generate(
        self,
        *,
        system_instructions: str,
        user_prompt: str,
        use_tools: bool,
    ) -> GenerationResult:
        # FoundryChatClient and FoundryToolbox are the official SDK adapters that
        # propagate x-agent-foundry-call-id automatically during hosted requests.
        tools = []
        if use_tools:
            tools.append(
                FoundryToolbox(
                self._credential,
                url=self._settings.toolbox_endpoint,
                name=self._settings.toolbox_name,
            )
            )
            if self._agent_mail is not None:
                tools.extend(
                    (
                        self._agent_mail.as_read_tool(),
                        self._agent_mail.as_send_tool(),
                    )
                )
        agent = Agent(
            client=self._client,
            id=self._settings.agent_name,
            name=self._settings.agent_name,
            description="Unified bank servicing orchestrator for Gartner demos 2 and 3.",
            instructions=system_instructions,
            tools=tools or None,
            default_options={"store": False},
        )
        async with agent:
            response = await agent.run(user_prompt)
        queried_sources, grounding_sources = _tool_activity(response)
        return GenerationResult(
            text=response.text,
            queried_sources=queried_sources,
            grounding_sources=grounding_sources,
            executed_actions=_successful_actions(response),
        )

    async def send_agent_email(
        self,
        *,
        recipient_emails: str,
        cc_emails: str,
        subject: str,
        body: str,
    ) -> GenerationResult:
        if self._agent_mail is None:
            raise RuntimeError("Agent 365 Work IQ mail is not configured")
        result = await self._agent_mail.send_email(
            recipient_emails,
            subject,
            body,
            cc_emails,
        )
        return GenerationResult(
            text=result,
            queried_sources=("Work IQ",),
            grounding_sources=("Work IQ",),
            executed_actions=("email_send",),
        )

    def _create_agent_mail_tool(self, settings: Settings) -> WorkIQMailTool | None:
        work_iq = settings.agent365_work_iq
        if work_iq is None:
            return None
        return WorkIQMailTool(
            project_endpoint=settings.project_endpoint,
            model_deployment=settings.model_deployment,
            credential=self._credential,
            expected_agent_user_id=work_iq.agent_user_id,
            token_provider=AgenticUserTokenProvider(
                tenant_id=work_iq.tenant_id,
                blueprint_client_id=work_iq.blueprint_client_id,
                instance_client_id=work_iq.instance_client_id,
                blueprint_secret_vault_url=work_iq.blueprint_secret_vault_url,
                blueprint_secret_name=work_iq.blueprint_secret_name,
                credential=self._credential,
            ),
            server=WorkIQMailServer(
                url=work_iq.mail_mcp_url,
                audience=work_iq.mail_mcp_audience,
            ),
        )


def _tool_activity(response: AgentResponse) -> tuple[tuple[str, ...], tuple[str, ...]]:
    call_sources: dict[str, str] = {}
    queried_sources: list[str] = []
    for message in response.messages:
        for content in message.contents:
            if content.type != "function_call" or not content.call_id or not content.name:
                continue
            source = _source_for_tool(content.name)
            if source is None:
                continue
            call_sources[content.call_id] = source
            if source not in queried_sources:
                queried_sources.append(source)

    grounding_sources: list[str] = []
    for message in response.messages:
        for content in message.contents:
            if content.type != "function_result" or not content.call_id:
                continue
            source = call_sources.get(content.call_id)
            if source is None or not _tool_result_has_data(content):
                continue
            if source not in grounding_sources:
                grounding_sources.append(source)
    return tuple(queried_sources), tuple(grounding_sources)


def _source_for_tool(tool_name: str) -> str | None:
    normalized = tool_name.casefold()
    for source, aliases in _TOOL_SOURCE_ALIASES:
        if any(alias in normalized for alias in aliases):
            return source
    return None


def _tool_result_has_data(content: Content) -> bool:
    if content.exception:
        return False
    result = content.result
    if result is None:
        return False
    if isinstance(result, str):
        return bool(result.strip())
    if isinstance(result, (list, tuple, dict, set)):
        return bool(result)
    return True


def _successful_actions(response: AgentResponse) -> tuple[str, ...]:
    call_names = {
        content.call_id: content.name
        for message in response.messages
        for content in message.contents
        if content.type == "function_call" and content.call_id and content.name
    }
    actions: list[str] = []
    for message in response.messages:
        for content in message.contents:
            if (
                content.type != "function_result"
                or not content.call_id
                or content.exception
                or not _tool_result_has_data(content)
            ):
                continue
            if call_names.get(content.call_id) == "send_agent_email":
                actions.append("email_send")
    return tuple(dict.fromkeys(actions))
