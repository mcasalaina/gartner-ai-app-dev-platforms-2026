# Foundry presenter evaluation

- Agent: `bank-servicing-agent` version `15`
- Invocation: precomputed responses with trusted `x-client-demo-mode`
- Cases: 6 synthetic, read-only cases
- Eval ID: `eval_f3221da710ee48b28885848b8aa35d6a`
- Run ID: `evalrun_72f0879909b64ffe8698e7ffad184fec`
- Status: `completed`
- Result counts: {"errored": 0, "failed": 6, "passed": 0, "skipped": 0, "total": 6}
- Custom rubric: `bank_servicing_rubric` version `1` (preview)
- Report: https://ai.azure.com/nextgen/r/J7ATmha0Qr-eycbbN2gkXg,rg-aycabas-3iqs,,4iq-foundry-project-resource,4iq-foundry-project/build/evaluations/eval_f3221da710ee48b28885848b8aa35d6a/run/evalrun_72f0879909b64ffe8698e7ffad184fec

| Evaluator | Mean score | Passed | Failed | Errored |
| --- | ---: | ---: | ---: | ---: |
| bank_servicing_rubric | n/a | 0 | 6 | 0 |
| indirect_attack | 1.000 | 6 | 0 | 0 |
| intent_resolution | 2.167 | 2 | 4 | 0 |
| relevance | 3.167 | 3 | 3 | 0 |
| task_adherence | 0.500 | 3 | 3 | 0 |

The standard Foundry agent-target runner cannot forward custom client headers.
This run therefore invoked the production agent first with the required trusted
mode header, then used Foundry's supported JSONL dataset-evaluation path to score
the resulting query/response pairs. No Work IQ response content was persisted in
this evaluation dataset.
