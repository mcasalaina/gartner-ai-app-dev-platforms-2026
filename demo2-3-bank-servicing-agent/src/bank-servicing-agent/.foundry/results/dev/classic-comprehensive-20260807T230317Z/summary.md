# Classic Foundry comprehensive evaluation

- Agent: `bank-servicing-agent` version `33`
- Inputs: 20 realistic, read-only banking requests
- Execution: classic OpenAI eval groups with correlated Foundry traces
- Tool evaluator pass/fail counts include only applicable cases; each run still contains all 20 output items.

| Evaluation | Run ID | Status | Output items |
| --- | --- | --- | ---: |
| response-quality | `evalrun_0583aa1efa6c49df9809d495f0ee8cf3` | completed | 20 |
| agent-outcomes | `evalrun_92d0c3d47a3a4339a9c35a200e270a56` | completed | 20 |
| intent-resolution | `evalrun_21d2bfa4cba243fb8bf2094f21da58b5` | completed | 20 |
| tool-quality | `evalrun_88a00ee20b174543b697c81a6494f805` | completed | 20 |

| Evaluator | Mean score | Passed | Failed | Errored |
| --- | ---: | ---: | ---: | ---: |
| fluency | 3.750 | 20 | 0 | 0 |
| groundedness | 4.500 | 19 | 1 | 0 |
| intent_resolution | 2.800 | 13 | 7 | 0 |
| relevance | 3.250 | 13 | 7 | 0 |
| task_adherence | 0.850 | 17 | 3 | 0 |
| task_completion | 0.500 | 10 | 10 | 0 |
| tool_call_accuracy | 4.000 | 10 | 3 | 0 |
| tool_call_success | 0.900 | 18 | 2 | 0 |
| tool_input_accuracy | 0.538 | 7 | 6 | 0 |
| tool_output_utilization | 0.706 | 12 | 5 | 0 |
| tool_selection | 1.000 | 13 | 0 | 0 |

## Failure clusters

| Evaluator | Non-passing or incomplete results |
| --- | ---: |
| groundedness | 1 |
| intent_resolution | 7 |
| relevance | 7 |
| task_adherence | 3 |
| task_completion | 10 |
| tool_call_accuracy | 10 |
| tool_call_success | 2 |
| tool_input_accuracy | 13 |
| tool_output_utilization | 8 |
| tool_selection | 7 |
