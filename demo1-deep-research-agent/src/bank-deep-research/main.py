# Copyright (c) Microsoft. All rights reserved.

import asyncio
import json
import logging
import os
import re
from typing import Any

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import FoundryToolbox
from azure.ai.agentserver.invocations import InvocationAgentServerHost
from azure.identity import DefaultAzureCredential
from azure.monitor.opentelemetry import configure_azure_monitor
from dotenv import load_dotenv
from starlette.requests import Request
from starlette.responses import JSONResponse

load_dotenv()
logging.getLogger("agent_framework").setLevel(logging.WARNING)
if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
    configure_azure_monitor(logger_name="gartner.deep_research.agent")

credential = DefaultAzureCredential()
project_endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
planner_client = FoundryChatClient(
    project_endpoint=project_endpoint,
    model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
    credential=credential,
)
research_clients = [
    FoundryChatClient(
        project_endpoint=project_endpoint,
        model=model,
        credential=credential,
    )
    for model in dict.fromkeys(
        (
            os.environ["AZURE_AI_RESEARCH_MODEL_DEPLOYMENT_NAME"],
            os.getenv("AZURE_AI_RESEARCH_MODEL_DEPLOYMENT_NAME_SECONDARY", ""),
        )
    )
    if model
]

planner = Agent(
    client=planner_client,
    instructions=(
        "You are the strategy planner for a regulated global investment bank. "
        "Return only valid JSON matching the requested schema. Decompose requests "
        "into decision-useful, independently researchable sections."
    ),
    default_options={"store": False},
)
editor = Agent(
    client=planner_client,
    instructions=(
        "You are a rigorous executive editor and research quality reviewer. "
        "Return only valid JSON. Preserve citation IDs, reject unsupported claims, "
        "and make disagreements between sources explicit."
    ),
    default_options={"store": False},
)
app = InvocationAgentServerHost()


def parse_json(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            raise
        return json.loads(cleaned[start : end + 1])


async def parse_or_repair_json(
    text: str, client: FoundryChatClient
) -> dict[str, Any]:
    try:
        return parse_json(text)
    except json.JSONDecodeError:
        repair_agent = Agent(
            client=client,
            instructions=(
                "You repair malformed JSON without changing its meaning. "
                "Return only one valid JSON object and no markdown fences."
            ),
            default_options={"store": False},
        )
        response = await repair_agent.run(
            "Repair this model response into valid JSON. Preserve every complete "
            f"field and value:\n\n{text}"
        )
        return parse_json(response.text)


async def build_plan(payload: dict[str, Any]) -> dict[str, Any]:
    prompt = f"""
Create a structured deep-research plan for this request:
{payload["prompt"]}

Research depth: {payload.get("research_depth", "executive")}
Multimodal context:
{json.dumps(payload.get("attachment_summaries", []), indent=2)}

Return exactly:
{{
  "plan": {{
    "refined_request": "string",
    "objectives": ["string"],
    "assumptions": ["string"],
    "methods": ["string"],
    "evaluation_criteria": ["string"],
    "sections": [
      {{
        "id": "kebab-case",
        "title": "string",
        "objective": "string",
        "search_questions": ["string"],
        "evaluation_criteria": ["string"]
      }}
    ],
    "revision": 1
  }}
}}
Create 4-6 sections covering market opportunity, regulation, operating model,
risk/control, technology, and service portfolio as appropriate.
"""
    response = await planner.run(prompt)
    return await parse_or_repair_json(response.text, planner_client)


async def research_section(
    section: dict[str, Any],
    context: dict[str, Any],
    client: FoundryChatClient,
) -> dict[str, Any]:
    toolbox = FoundryToolbox(credential)
    researcher = Agent(
        client=client,
        instructions=(
            "You are a specialist deep-research agent. Use only the available "
            "Microsoft Web IQ toolbox for live grounding. Every externally verifiable "
            "claim must cite a source. Return only valid JSON."
        ),
        tools=toolbox,
        default_options={"store": False},
    )
    prompt = f"""
Research this approved assignment for a bank operating in the US, Europe, and China:
{json.dumps(section, indent=2)}

Overall request: {context["prompt"]}
Evaluation criteria: {json.dumps(context["plan"]["evaluation_criteria"])}

Use no more than three focused Web IQ searches. For every web search, request
contentFormat "passage", maxResults 5, and maxLength 6000. Prefer regulators,
exchanges, official statistics, audited filings, and recent authoritative sources.
Select only evidence needed to support the section; do not retrieve full documents.
Return exactly:
{{
  "section_id": "{section["id"]}",
  "title": "{section["title"]}",
  "markdown": "cited section using [source-id] markers",
  "citations": [
    {{
      "id": "source-id",
      "title": "source title",
      "url": "https://...",
      "publisher": "publisher",
      "published_at": "date or null",
      "claims": ["claim supported by this source"]
    }}
  ],
  "conflicts": ["material source disagreement"],
  "confidence": 0.0
}}
Keep markdown under 900 words, include at most 12 citations, and include at most
three claims per citation so the complete JSON response is not truncated.
"""
    async with researcher:
        response = await researcher.run(prompt)
    return await parse_or_repair_json(response.text, client)


async def synthesize(
    payload: dict[str, Any], sections: list[dict[str, Any]], repair: bool = False
) -> dict[str, Any]:
    prompt = f"""
Synthesize the approved bank research plan and specialist evidence into a concise,
decision-ready report. This is {"a single bounded repair pass" if repair else "the initial quality pass"}.

Approved plan:
{json.dumps(payload["plan"], indent=2)}

Specialist evidence:
{json.dumps(sections, indent=2)}

Return exactly:
{{
  "report_markdown": "comprehensive report with inline [source-id] citations",
  "highlighted_chapter": "standalone Recommended Banking Services chapter",
  "citations": [
    {{
      "id": "source-id",
      "title": "title",
      "url": "https://...",
      "publisher": "publisher or null",
      "published_at": "date or null",
      "claims": ["supported claim"]
    }}
  ],
  "evaluation": {{
    "groundedness": 0.0,
    "citation_completeness": 0.0,
    "plan_coverage": 0.0,
    "source_quality": 0.0,
    "passed": true
  }},
  "service_scores": {{
    "Commercial banking": 0,
    "Investment services": 0,
    "Compliance automation": 0,
    "Fraud prevention": 0
  }}
}}
Scores are 0-1 for evaluation and 0-100 for service priorities. Deduplicate
citations by canonical URL. Do not invent sources, URLs, dates, or claims.
Keep the complete report under 2,500 words so the JSON object is not truncated.
"""
    response = await editor.run(prompt)
    return await parse_or_repair_json(response.text, planner_client)


async def run_research(payload: dict[str, Any]) -> dict[str, Any]:
    sections = payload["plan"]["sections"]
    lane_count = min(
        int(os.getenv("RESEARCH_CONCURRENCY", "2")),
        len(research_clients),
        len(sections),
    )
    assignments = [list() for _ in range(lane_count)]
    for index, section in enumerate(sections):
        assignments[index % lane_count].append((index, section))

    async def run_lane(
        lane: int, work: list[tuple[int, dict[str, Any]]]
    ) -> list[tuple[int, dict[str, Any]]]:
        results = []
        for index, section in work:
            result = await research_section(section, payload, research_clients[lane])
            results.append((index, result))
        return results

    completed_lanes = await asyncio.gather(
        *(run_lane(lane, work) for lane, work in enumerate(assignments))
    )
    findings = [
        result
        for _, result in sorted(
            (item for lane in completed_lanes for item in lane),
            key=lambda item: item[0],
        )
    ]
    result = await synthesize(payload, findings)
    if not result["evaluation"]["passed"]:
        result = await synthesize(payload, findings, repair=True)
    return result


@app.invoke_handler
async def handle_invoke(request: Request):
    data = await request.json()
    raw_message = data.get("message")
    if not isinstance(raw_message, str):
        return JSONResponse({"error": "Missing string 'message'."}, status_code=400)
    try:
        payload = json.loads(raw_message)
        action = payload.get("action")
        if action == "plan":
            result = await build_plan(payload)
        elif action == "research":
            result = await run_research(payload)
        else:
            return JSONResponse(
                {"error": f"Unsupported action: {action}"}, status_code=400
            )
        return JSONResponse({"response": json.dumps(result)})
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


if __name__ == "__main__":
    app.run()
