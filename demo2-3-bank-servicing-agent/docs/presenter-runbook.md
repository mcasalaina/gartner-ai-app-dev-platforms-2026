# Bank Servicing Agent presenter runbook

This runbook covers Gartner Demos 2 through 4 as three trusted modes of the same
Microsoft Foundry hosted agent. Use synthetic identities and records only.

## Preflight

1. Confirm the deployed agent is `bank-servicing-agent` in
   `4iq-foundry-project` and production resolves to `gpt-5.4-mini`.
2. Confirm the frontend and backend are on the intended presentation revisions.
3. Confirm the presenter has `BankServicing.Access`. Use
   `BankServicing.ContentReviewer` for review and `BankServicing.Admin` for the
   model comparison lab.
4. Confirm Voice Live is in East US 2 and configured with the standard Amara
   photo avatar, `vasa-1`, `en-US-AvaMultilingualNeural`, multilingual semantic
   VAD, and WebRTC output.
5. In the presentation browser, allow microphone access and confirm Amara video,
   synchronized audio, and live transcripts. Custom photo-avatar and personal
   voice approvals are not required for this flow.
6. Run the Foundry smoke suite and the ASSERT smoke validation. Stop if a hard
   gate or trace-completeness gate fails.
7. Keep the existing `acme-bank-servicing-agent` and legacy Agent 365 bridge
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
- Voice Live uses a backend-issued, single-use handle. Avatar signaling, OBO
  credentials, and reusable Voice Live credentials stay behind the backend.
- Hosted-agent calls have a bounded 90-second upstream timeout.
- Agent 365 standalone cutover validation is separate from this OBO baseline.

## Demo 2: service discovery

1. Open the public web shell and show that no agent control is available before
   sign-in. Sign-in stays in the same window.
2. Sign in and select **Explore services**.
3. Ask for a detailed service recommendation. Point out citations to the
   separate Demo 1 service corpus and approved content version.
4. Use text chat for the service follow-up and show that the answer remains
   grounded in the approved content path.
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

## Demo 4: multilingual talking avatar

1. Select **Explore services**, set the tone to **Professional**, and start
   **Talk with Avatar**. Show Amara moving from Connecting to Listening.
2. Ask in English: “Compare checking and savings services and explain the main
   benefit of each.” Point out the synchronized video, Ava multilingual voice,
   live transcript, and grounded banking answer.
3. Set the tone to **Warm** and ask in Spanish: “Quiero abrir una cuenta. ¿Cómo
   verifico mi identidad?” Show the same avatar answering in Spanish and the
   visible workspace automatically moving to **Customer servicing** with a
   navigation notice.
4. Set the tone to **Energetic** and ask: “Take me back to compare your banking
   products.” Show the allowlisted move to **Explore services**. Explain that
   navigation can only select the two existing banking workspaces and cannot
   execute a transaction.
5. Ask for the approved service imagery used by the recommendation and point out
   that it follows the existing Demo 2 content and review path.
6. Ask an unrelated question, then a salary or hidden-prompt request. Show that
   the same domain, DLP, prompt-injection, and cross-user controls still apply
   before tools.
7. End the call and show that microphone, avatar stream, peer connection, and
   audio resources are released while text chat remains available.

If avatar WebRTC cannot connect, end the call and continue with text chat. Do not
switch to a custom avatar or personal voice unless the corresponding
limited-access approvals have been confirmed for this subscription.

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
