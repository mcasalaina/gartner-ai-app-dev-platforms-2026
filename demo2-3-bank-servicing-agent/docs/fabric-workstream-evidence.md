# Fabric workstream evidence

Validated against the live tenant on 2026-08-04 Pacific time
(2026-08-05 UTC). All customer, account, transaction, fee, loan, and collections
records referenced here are synthetic demo data.

## Asset identity and reuse conclusion

The current Gartner Demos 2 and 3 implementation does **not** use the original
`bank-agent-a365` Fabric item IDs. It uses a newer live Fabric estate with the
same logical ACME Bank names. The old Foundry project still exists, but the old
Fabric workspace returns `WorkspaceNotFound`.

### Current live implementation

| Surface | Name | ID / target |
|---|---|---|
| Fabric workspace | `AcmeBank.Workspace` | `ae8eaa7c-5ace-4256-967f-25c84dc9313a` |
| Capacity | `cap3iqs5ea837a6` (East US 2, F16, active) | `24f6590d-413b-4d9f-9c2b-601d753eda94` |
| Servicing lakehouse | `AcmeBankServicing` | `3deccb3c-3baa-49a9-be85-daaed6898fe7` |
| Servicing SQL endpoint | `AcmeBankServicing` | `e2655fe0-834c-4f8e-9e2d-460ee01179ce` |
| Loans lakehouse | `AcmeBankLoansCredit` | `6c624bf1-63b7-4f04-bd01-ceddbbc59d8e` |
| Loans SQL endpoint | `AcmeBankLoansCredit` | `93cb4f54-520e-46f4-9603-ace34fd95efe` |
| Semantic model | `AcmeBankServicing SM` | `ba8c0709-7224-4248-bef8-532dc1a831af` |
| Power BI report | `AcmeBankServicing Report` | `8648f7bf-be5e-4f4f-a4a9-67f67e1a2bc8` |
| Ontology | `AcmeBankServicingOntology` | `00788d8a-bf54-41bf-9f37-b875b8586fa5` |
| Backing graph | `AcmeBankServicingOntology_graph_00788d8abf5441bf9f37b875b8586fa5` | `48a6a3a8-6e88-4f06-b33a-242b983ef47d` |
| Ontology lakehouse | `AcmeBankServicingOntology_lh_00788d8abf5441bf9f37b875b8586fa5` | `dfc8b0a8-ef40-4682-b584-cbe86ec80d53` |
| Ontology SQL endpoint | same logical name as ontology lakehouse | `794868e1-f662-4466-8cdf-a8a669a1851f` |
| Fabric Data Agent | `AcmeBankServicingAgent` | `90371bd6-280d-40a4-aaff-f153be2e63bc` |

The report is bound to `AcmeBankServicing SM`. The semantic model is Direct
Lake over `AcmeBankServicing`. The Data Agent has the ontology, servicing
lakehouse, and loans lakehouse published as sources.

The current Foundry project is `4iq-foundry-project` at
`https://4iq-foundry-project-resource.services.ai.azure.com/api/projects/4iq-foundry-project`.
Its `fabric-iq-acmebank` RemoteTool connection uses `UserEntraToken` and targets:

```text
https://api.fabric.microsoft.com/v1/mcp/workspaces/ae8eaa7c-5ace-4256-967f-25c84dc9313a/dataagents/90371bd6-280d-40a4-aaff-f153be2e63bc/agent
```

The current toolbox also names `WorkIQ` and `kb-acme-bank-foundryiq`.

### Original `bank-agent-a365` implementation

| Surface | Last-known name | Last-known ID / status |
|---|---|---|
| Foundry project | `3iqs-aycabas-westus` | Live project in West US |
| Fabric workspace | `AcmeBank.Workspace` | `5a8a2105-b1c7-4f0c-ad37-c72e6937de56`; now returns `WorkspaceNotFound` |
| Servicing lakehouse | `AcmeBankServicing` | `2f833df9-1067-4d52-8f1e-656b17a60e38` |
| Servicing semantic model | `AcmeBankServicing` | only prefix `7de24236…` was recorded in source |
| Power BI report | report definition in `report/` | no live report ID was recorded; deployment was documented as deferred |
| Ontology | `AcmeBankServicingOntology` | `bd7af666-5eb9-411d-bd8a-2005b44efddd` |
| Data Agent | `AcmeBankServicingAgent` | `c6309538-61ba-4bac-bc59-373dfd86bd8f` |
| Loans lakehouse | `AcmeBankLoansCredit` | `559f406f-e10e-4a78-ae8d-ebcca8c89ecb` |
| Loans SQL endpoint | `AcmeBankLoansCredit` | `6d87e632-057c-4fdb-a9f7-3ac99ff2d6f5` |

The old Foundry project still exposes an opaque
`fabric_dataagent_acmebank` CustomKeys connection and
`kb-acme-bank-foundryiq` / `kb-acme-bank-foundryiq-2` RemoteTool connections.
It does not expose the current project's `fabric-iq-acmebank` RemoteTool
connection. No secret material was read or recorded.

## Synthetic date update

The live current lakehouses were shifted with one constant `+61 day` offset.
The pre-update maximum operational timestamp, `2026-06-04 03:01:00`, became
`2026-08-04 03:01:00`. A single offset was used across both lakehouses so
durations, event order, account tenure, loan age, payment cadence, and
cross-table joins remain coherent. The update was idempotent: it no-ops when
the maximum operational date is already 2026-08-04.

| Field | Rows | Before | After |
|---|---:|---|---|
| `accounts.opened_at` | 13 | 2015-05-24 .. 2025-05-21 | 2015-07-24 .. 2025-07-21 |
| `fees.assessed_date` | 11 | 2026-05-17 .. 2026-06-04 | 2026-07-17 .. 2026-08-04 |
| `transactions.posted_at` | 26 | 2026-05-16 00:00 .. 2026-06-04 03:01 | 2026-07-16 00:00 .. 2026-08-04 03:01 |
| `collections.opened_date` | 5 | 2026-02-16 .. 2026-05-03 | 2026-04-18 .. 2026-07-03 |
| `credit_scores.pulled_date` | 36 | 2026-05-08 .. 2026-05-21 | 2026-07-08 .. 2026-07-21 |
| `loan_payments.payment_date` | 281 | 2011-08-08 .. 2026-05-03 | 2011-10-08 .. 2026-07-03 |
| `loans.origination_date` | 16 | 2011-07-09 .. 2025-10-23 | 2011-09-08 .. 2025-12-23 |

Seven temporal fields and 388 field values changed. Row counts, identifiers,
amounts, statuses, relationships, and non-date values did not change. No
date-like string fields were found. The successful Fabric notebook job was
`fbef97d4-4ba0-4b6f-bb92-17f1f398920c`; its temporary notebook was deleted.

Both Lakehouse SQL endpoint metadata surfaces were synchronized. Direct Lake
semantic-model refresh request `b44a7374-a595-4eb6-af1b-baaa7e0c573c`
completed successfully. Ontology re-save and Data Agent republish were not
needed because their published bindings already point to the live Delta
tables; both surfaces returned the shifted data.

## Verification evidence

### Power BI report and semantic model

The report metadata and all three pages opened, and the bound model returned
live rows:

- **Transactions & Fees Trends:** Fees Assessed Over Time, Transaction Amount
  Over Time, Transaction Amount by Type, Overdraft Cascade.
- **Fee Reversal Overview:** Fees Assessed by Fee Type, Fees by Reversal
  Eligibility, Fees Assessed by Customer Type.
- **Accounts & Branches:** Accounts by Home Branch, Accounts by Type, Branches
  by Region, Average Balance by Account Type.

For synthetic customer Sarah Chen and `ACC-1001`, the model returned an active
premier checking account with balance `-$245.00`, home branch `BR-SEA`, four
overdraft fees of `$35.00` each on 2026-07-20, and all four fees eligible for
reversal. The nine-event cascade runs from the payroll deposit on 2026-07-18
through the fourth fee at 2026-07-20 20:30. The model's latest servicing
timestamp is 2026-08-04 03:01.

### Ontology

The ontology definition opens and binds Branch, Banker, Customer, and Account
to the live servicing lakehouse. A live graph query for `ACC-1001` returned:

- Customer: Sarah Chen (`CUST-001`)
- Servicing banker: Kim Patel (`BKR-001`)
- Account branch: Acme Bank Seattle (`BR-SEA`)
- Banker branch: Acme Bank Seattle (`BR-SEA`)

The graph does not model Fee or Transaction as entity types. Fee facts are
therefore supplied by the Data Agent's lakehouse source, not by graph traversal.

### Fabric Data Agent

The published Data Agent definition opens and advertises
`DataAgent_AcmeBankServicingAgent`. A delegated-user MCP query returned
`FEE-0001` through `FEE-0004`, each `$35.00`, assessed 2026-07-20, together
with Kim Patel and Acme Bank Seattle. A second query returned the latest
servicing event as **August 4, 2026 at 3:01 AM**.

## Presenter portal path

1. Open the
   [AcmeBank.Workspace](https://app.fabric.microsoft.com/groups/ae8eaa7c-5ace-4256-967f-25c84dc9313a).
2. Open
   [AcmeBankServicing Report](https://app.fabric.microsoft.com/groups/ae8eaa7c-5ace-4256-967f-25c84dc9313a/reports/8648f7bf-be5e-4f4f-a4a9-67f67e1a2bc8).
   Show **Fee Reversal Overview**, then **Transactions & Fees Trends** for the
   shifted fee and cascade dates.
3. Return to the workspace and open **AcmeBankServicing SM**. Confirm the seven
   tables and use the model query experience if a data proof point is needed.
4. Open
   [AcmeBankServicingOntology](https://app.fabric.microsoft.com/groups/ae8eaa7c-5ace-4256-967f-25c84dc9313a/ontologies/00788d8a-bf54-41bf-9f37-b875b8586fa5).
   Show Account, Customer, Banker, and Branch plus their five relationships.
5. Open
   [AcmeBankServicingAgent](https://app.fabric.microsoft.com/groups/ae8eaa7c-5ace-4256-967f-25c84dc9313a/aiskills/90371bd6-280d-40a4-aaff-f153be2e63bc).
   Ask: `For ACC-1001, list the overdraft fees with assessed dates and identify
   the servicing banker and branch. What is the latest servicing event date?`

If a direct item link redirects, open the workspace first and select the item
by the exact name above.

## Blockers

- No blocker exists for the current live demo surfaces.
- The original workspace cannot be inventoried beyond source-recorded IDs
  because Fabric currently returns `WorkspaceNotFound`.
- The current ontology does not directly model Fee and Transaction entities;
  the Data Agent correctly answers those facts from its lakehouse sources.

