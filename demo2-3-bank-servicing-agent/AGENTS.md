# Coding Agent Instructions

This folder implements Gartner Demos 2 through 4 as one Microsoft Foundry hosted
agent and authenticated web application.

## Requirements

- This project was built with the `microsoft-foundry` skill. Before working on
  or answering questions about Foundry agents, read the `microsoft-foundry`
  skill first.
- Keep `gpt-5.4-mini` as the production model.
- Use the Responses protocol version 2.0.0.
- Require Microsoft Entra authentication before any agent interaction.
- Preserve caller identity through `x-agent-foundry-call-id`; never forward or
  log bearer tokens.
- Use the standard Amara photo avatar with `en-US-AlloyTurboMultilingualNeural` for
  Voice Live until custom photo avatar and personal voice access is approved.
- Treat rubric evaluators and Agent Optimizer as preview and ASSERT as beta.
- Use only synthetic customer and KYC data.
- Never weaken bank-domain, salary-DLP, cross-user isolation, or explicit
  confirmation gates to make a demo pass.

## Validation

Run the smallest relevant tests for each component:

- Agent: `python -m pytest src/bank-servicing-agent/tests`
- Web backend: `python -m pytest web/backend/tests`
- Web frontend: `npm run lint && npm run test && npm run build`
- ASSERT: `python -m pytest evaluation/assert/tests`
