# Bank Servicing Agent presenter runbook

This runbook covers Gartner Demos 2 and 3 as two modes of the same Microsoft
Foundry hosted agent. Use synthetic identities and records only.

## Preflight

1. Confirm the deployed agent is `bank-servicing-agent` in
   `4iq-foundry-project`, the active version is 6, and production resolves to
   `gpt-5.4-mini`.
2. Confirm the web API revision uses backend image `20260804.5` and the
   frontend revision uses image `20260804.7`.
3. Confirm the presenter has `BankServicing.Access`. Use
   `BankServicing.ContentReviewer` for review and `BankServicing.Admin` for the
   model comparison lab.
4. Confirm Voice Live is configured with
   `en-US-Davis:DragonHDLatestNeural`.
5. Run the Foundry smoke suite and the ASSERT smoke validation. Stop if a hard
   gate or trace-completeness gate fails.
6. Keep the existing `acme-bank-servicing-agent` and legacy Agent 365 bridge
   revision available for rollback.

The presenter sign-in uses a same-window redirect, not a popup. MSAL stores
redirect and token state in tab-scoped `sessionStorage`; closing the isolated
presenter tab clears that state.

## Verified OBO baseline

- Service discovery and customer servicing both complete through the signed-in
  SPA, API token validation, confidential-client OBO, hosted agent, and Toolbox.
- Same-conversation follow-ups retain context.
- Salary DLP, non-bank refusal, and the next valid banking turn remain
  independent; a blocked turn does not poison later turns.
- Voice Live uses a backend-issued, single-use handle. A live spoken-input test
  returned both Azure Speech transcription and Davis audio.
- Hosted-agent calls have a bounded 90-second upstream timeout.
- Agent 365 standalone cutover validation is separate from this OBO baseline.

## Demo 2: service discovery

1. Open the public web shell and show that no agent control is available before
   sign-in. Sign-in stays in the same window.
2. Sign in and select **Explore services**.
3. Ask for a detailed service recommendation. Point out citations to the
   separate Demo 1 service corpus and approved content version.
4. Start **Talk with Davis**, ask a follow-up, interrupt once, and show the live
   transcript.
5. Show an approved service image or generate a proposed image. Explain that
   generated media is not published until review.
6. Open **Quality & review** as a reviewer, approve or reject the pending
   synthetic draft, and show the immutable version change.

## Demo 3: customer servicing

1. Select **Customer servicing** without changing agents or identities.
2. Ask for synthetic account and investment status. Point out that the signed-in
   caller is preserved through OBO and user-scoped tools.
3. Start a synthetic checking-account application. Show the bounded KYC draft,
   review summary, and explicit confirmation requirement.
4. Ask for an unrelated task and show the bank-domain refusal before tools.
5. Enter a salary/payroll probe and show the content-free DLP event with no
   downstream data call.
6. Attempt a hidden-prompt or cross-user request and show the hard-gate refusal.

## Quality, A/B, and feedback

1. Submit positive or negative feedback on a response. Only trace ID, sentiment,
   policy dimensions, and redacted reviewer notes are eligible for curation.
2. As an administrator, open the model comparison lab. Run the same synthetic
   prompt against `gpt-5.4-mini`, `gpt-5-mini`, and `gpt-4.1-mini`.
3. State that customer traffic remains fixed to `gpt-5.4-mini`; comparison
   outputs never become a live traffic split.
4. Explain that Foundry rubric evaluators and Agent Optimizer are preview and
   ASSERT is beta. Deterministic gates remain independent evidence.
5. Show that unavailable rubric, ASSERT, or cost data is labeled **Not
   available**, never displayed as a fabricated score.

## Rollback

1. Stop bridge cutover and route Agent 365 back to the retained legacy bridge
   revision.
2. Repoint the presentation link to the last healthy web revision.
3. Keep the new hosted agent and data assets for investigation; do not delete or
   overwrite the existing prompt agent or knowledge sources.
4. Record the failing response ID and trace ID without copying customer content.
