# Multi-source intro evaluation

- Timestamp: `2026-08-05T04:43:35.748932+00:00`
- Run ID: `20260805T044300Z`
- Agent: `bank-servicing-agent` version `7`
- Azure job execution: `bank-servicing-assert-aaizrhw`
- Evaluation identity: Agent ID user via loopback Entra auth sidecar
- Passed: `false`
- Hard failure: `true`
- Required sources: `Fabric IQ, Foundry IQ, Work IQ`
- Successful tool evidence: `none`
- Observed source line: `missing`
- Response SHA-256: `d6ad6c47a60c944c5cc0eb2b125dbe70c5582de5e2d7ee9bf087e90f7ebc338c`

## Failures

- Required tools returned no data: Fabric IQ, Foundry IQ, Work IQ
- Expected exactly one Sources used line; found 0


The response body is intentionally not persisted because Work IQ may return workplace content. A source is counted only when the remote response includes a successful, non-empty MCP tool result for that source.
