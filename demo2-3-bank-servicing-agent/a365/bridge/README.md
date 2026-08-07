# Agent 365 bridge

This component replaces the legacy bridge while preserving the existing Agent 365
blueprint, Teams presence, mailbox, and standalone agent-user identity. It obtains
an autonomous agent-user token from the loopback Entra Auth SDK sidecar, validates
the token claims locally, and invokes the `bank-servicing-agent` Responses
endpoint. It never exchanges or forwards the human caller's OBO token.

The production process listens on port 8080 and exposes:

- `POST /api/messages` for authenticated Agent 365 activity protocol traffic.
- `GET /health` and `GET /api/health` for Container Apps probes.

When `BRIDGE_IDENTITY_SMOKE_ENABLED=true`, each replica runs one synthetic
fee-dispute readiness turn after startup. Health reports only
`identityReadiness: pending|ready|failed`; it never returns a token or response
content. Foundry requests use the same bounded 90-second timeout as the verified
web path so grounded fee triage can complete.

Inbound email is accepted only when clearly labeled `[SYNTHETIC DEMO]`. The bridge
blocks salary/payroll content, cross-customer requests, and non-bank messages
before Foundry. A valid fee dispute is grounded and stored as a pending case. The
customer receives an acknowledgement that no fee was changed. An employee can
review and explicitly confirm or escalate the case in Teams:

```text
review fee dispute FD-0123456789
confirm fee dispute FD-0123456789
escalate fee dispute FD-0123456789
```

Confirmation produces a customer-ready draft or employee handoff only. No fee
write tool is configured, so the bridge never claims a reversal was executed.
