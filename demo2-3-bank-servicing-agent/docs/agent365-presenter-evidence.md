# Gartner Demo 3: Agent 365 presenter evidence

Evidence refreshed 2026-08-06 01:21 UTC. This document contains only
nonproduction demo content and non-secret resource metadata.

## Presenter claim

Demo 3 uses the preserved standalone Agent 365 identity, not the presenter's
OBO identity. The bridge acquires an agent-user token from its loopback Entra
Auth SDK sidecar and invokes the same Microsoft Foundry hosted agent used by the
signed-in web experience.

## Agent 365 identity

| Item | Verified value |
|---|---|
| Display name | `Marco's Teller` |
| Agent-user object ID | `a7a91f6a-1c79-43f3-9653-c6a728d64f9c` |
| Agent identity ID | `439176bf-94bd-497f-985b-a3c93cc989b2` |
| Parent blueprint app ID | `2c3685f3-7ad7-467b-96e8-dd3d06b99f55` |
| Parent blueprint display name | `acmebank Blueprint` |
| Mailbox / UPN | `marcos-teller@cam3652609.onmicrosoft.com` |
| Directory state | Enabled member user and enabled service identity |
| Owner / manager | `Marco Casalaina (BAMI)` |

The unused legacy `marcosteller@cam3652609.onmicrosoft.com` instance, user, and
service identity were permanently removed. One active instance remains.

`a365 query-entra inheritance` verified effective inheritance for all nine
configured resources. The Microsoft Graph delegated grant has eight scopes:

- `Mail.ReadWrite`
- `Mail.Send`
- `Chat.ReadWrite`
- `User.Read.All`
- `Sites.Read.All`
- `Files.Read.All`
- `ChannelMessage.Read.All`
- `ChannelMessage.Send`

`Files.ReadWrite.All` is not granted.

## Agent Registry publication

| Item | Verified value |
|---|---|
| Template | `Bank Servicing Agent Template` |
| Status | **Available** |
| Version | `2.0.2` |
| Channel | Copilot |
| Publisher / type | `Marco Casalaina` / `Your org` |
| Entra agent ID | `2c3685f3-7ad7-467b-96e8-dd3d06b99f55` |
| Active instances | 1 |
| Active instance | `marcos-teller@cam3652609.onmicrosoft.com` |

The registry also lists `bank-servicing-agent` as a separate Microsoft Foundry
agent. `Bank Servicing Agent Template` is the Agent 365 template, while
`Marco's Teller` is its active named instance.

## Teams discovery

The presenter account can discover the exact `Marco's Teller` agent in Teams.
Selecting it opened `Chat | Marco's Teller | Microsoft Teams`.

Presenter navigation:

1. Open Microsoft Teams.
2. Search for `Marco's Teller`.
3. Select the exact agent identity.
4. If cached results are stale, refresh Teams and search again.

## Live bridge and Foundry resources

| Item | Live value |
|---|---|
| Container App | `marcos-teller-bridge-a365` |
| Ready revision | `marcos-teller-bridge-a365--0000019` |
| Bridge image | `shipmentdashboardacr.azurecr.io/marcos-teller-bridge-a365:20260805.8` |
| Bridge image digest | `sha256:29fda269d4abc507d5b57e5608a103d1ed8830c773a157f5124c2cd511fc4d37` |
| Bridge FQDN | `marcos-teller-bridge-a365.gentleforest-8d33b38e.westus.azurecontainerapps.io` |
| Entra sidecar | `mcr.microsoft.com/entra-sdk/auth-sidecar@sha256:495ec1a7142b3e016b7d9b96ca73cfc6bb504f1c6b4ce07647dd5723275b1b7b` |
| Foundry project | `4iq-foundry-project` |
| Hosted agent | `bank-servicing-agent` |
| Active Foundry version | `24` |
| Protocol | Responses `2.0.0` |
| Production model | `gpt-5.4-mini` |

The current external health response is:

```json
{"status":"ok","identityMode":"agent_user","identityReadiness":"ready","agent":"bank-servicing-agent"}
```

## Inbound email activation proof

Maria Garcia sent a normal customer email from
`mariagarcia@cam3652609.onmicrosoft.com` to the active Agent 365 mailbox.

```text
Subject: Does the $35 ATM fee on checking ending in 1013 qualify for a refund?

Hi Marco's Teller,

I noticed a $35 ATM fee on my checking account ending in 1013 after a
withdrawal this week. Does it qualify for a refund, and does anyone need to
approve it?

Please cc Marco Casalaina at
mcasalaina.local@cam3652609.onmicrosoft.com on your reply so he has the answer.

Thanks,
Maria
```

Outlook applied `General - All Employees (unrestricted)` to the inbound
message. The active agent woke and created a threaded reply through Microsoft
Graph using its own user-FIC identity.

| Reply evidence | Verified value |
|---|---|
| Subject | `RE: Does the $35 ATM fee on checking ending in 1013 qualify for a refund?` |
| From / sender | `marcos-teller@cam3652609.onmicrosoft.com` |
| To | `mariagarcia@cam3652609.onmicrosoft.com` |
| Cc | `mcasalaina.local@cam3652609.onmicrosoft.com` |
| Sent time | `2026-08-06T01:20:44Z` |
| Sent Items count for exact subject | 1 |
| Draft state | `false` |
| General label | Present |
| Label content bits / method | `1` / `Standard` |

The agent, not Marco's account, sent the reply. Marco has no Send As or Send on
Behalf permission for this mailbox.

## Reply controls

The Agent 365 SDK's built-in `EmailResponse` supports only an HTML body. It
cannot set Cc recipients or a Purview sensitivity label. The bridge therefore
uses this agent-owned Graph sequence:

1. Exchange the parent blueprint and instance credentials for the Agent 365
   user's Graph token.
2. Call `createReply` on the inbound message to preserve the thread.
3. Update the draft body and an explicitly requested, allowlisted Cc recipient.
4. Add and verify the `MSIP_Labels` extended property for
   `All Employees (unrestricted)`.
5. Verify draft state, recipients, and label metadata.
6. Send the verified draft once.

The Cc allowlist contains only
`mcasalaina.local@cam3652609.onmicrosoft.com`. An address appearing elsewhere
in the message is not copied unless the customer explicitly requests Cc or
copying that address.

The customer response is bounded. It never claims a refund, reversal, or waiver
was completed. If the grounded response cannot be safely reduced to
customer-ready text, the bridge sends a case acknowledgement that states no
fee has changed and employee confirmation is still required.

## Live validation results

| Validation | Result |
|---|---|
| Standalone identity sidecar | Passed |
| Agent-user claim validation | Passed |
| Own-identity Foundry call | HTTP `200` |
| Bridge readiness | `identityReadiness=ready` |
| Hosted agent | Version `24`, active |
| Production model | `gpt-5.4-mini` |
| Agent 365 inheritance | 9 of 9 resources effective |
| Graph delegated scopes | 8; read-only file access |
| Active Agent 365 instances | 1 |
| Bridge tests | 17 passed |
| Ruff | Passed |
| ACR build | Run `cf1m`, succeeded |
| Inbound delivery | Confirmed in Maria's Sent Items and by agent activation |
| Threaded agent reply | Confirmed |
| Reply Cc | Confirmed in Outlook and Graph |
| Reply General label | Confirmed in Outlook and Graph |
| Agent Sent Items | Exactly one message for the final subject |
| Exchange admin tab | Closed |

## Presenter sequence

1. Open Maria Garcia's Sent Items and show the natural inbound subject.
2. Open Maria Garcia's Inbox and show the threaded reply from `Marco's Teller`.
3. Expand the message header to show Maria in To and Marco in Cc.
4. Show `General - All Employees (unrestricted)` on the reply.
5. Show bridge health with `identityMode=agent_user` and
   `identityReadiness=ready`.
6. In Microsoft Foundry, show hosted agent version `24`, the Responses protocol,
   and `gpt-5.4-mini`.

This proves inbound Agent 365 activation, standalone identity, threaded
agent-owned reply, requested Cc handling, General labeling, and the no-write
employee-confirmation boundary.
