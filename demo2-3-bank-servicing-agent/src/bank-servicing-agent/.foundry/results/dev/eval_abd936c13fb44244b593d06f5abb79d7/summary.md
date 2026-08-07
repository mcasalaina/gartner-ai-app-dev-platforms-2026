# Foundry evaluation evidence

All runs target hosted `bank-servicing-agent` version `6` and completed remotely
on `2026-08-05`.

| Run | Run ID | Result |
| --- | --- | --- |
| bank-servicing-smoke-v6-20260804 | `evalrun_4e688afc6e264b1197247970eb6681ef` | 0/3 passed |
| bank-servicing-pdf-fidelity-v6-20260804 | `evalrun_d666af4dfc7245de9086176f35eed989` | 0/3 passed |
| bank-servicing-dlp-v6-20260804 | `evalrun_1b0a904657fa4527bf2f145536e59538` | 0/3 passed |

Mean scores (smoke / PDF / DLP): relevance `2.0 / 1.0 / 1.0`,
task adherence `0 / 0 / 0`, intent resolution `1.0 / 1.0 / 1.0`, and
indirect attack `1.0 / 1.0 / 1.0`. Tool-call accuracy had no numeric score.

Every response failed closed on the required `x-client-demo-mode` header.
`indirect_attack` passed all nine rows. Relevance, task adherence, and intent
resolution failed all nine rows. Tool-call accuracy errored because no tool
definitions were emitted. The custom bank rubric was not remotely available, so
these runs use verified Foundry built-ins only.
