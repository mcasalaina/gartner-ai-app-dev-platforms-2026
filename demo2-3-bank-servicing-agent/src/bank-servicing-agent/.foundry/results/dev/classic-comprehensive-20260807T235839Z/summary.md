# Classic Foundry comprehensive evaluation

- Agent: `bank-servicing-agent` version `33`
- Inputs: 20 realistic, read-only banking requests
- Execution: one classic Foundry evaluation run with all requested built-in evaluators
- Tool evaluator pass/fail counts include only applicable cases; each run still contains all 20 output items.

| Evaluation | Run ID | Status | Output items |
| --- | --- | --- | ---: |
| standard-comprehensive | `evalrun_f98b52fbaab54defb6a53989419afe0f` | completed | 20 |

| Evaluator | Mean score | Passed | Failed | Errored |
| --- | ---: | ---: | ---: | ---: |
| fluency | 3.750 | 20 | 0 | 0 |
| groundedness | 4.750 | 20 | 0 | 0 |
| intent_resolution | 3.000 | 14 | 6 | 0 |
| relevance | 3.350 | 15 | 5 | 0 |
| task_adherence | 0.900 | 18 | 2 | 0 |
| task_completion | 0.500 | 10 | 10 | 0 |
| tool_call_accuracy | 4.077 | 10 | 3 | 0 |
| tool_call_success | 0.895 | 17 | 2 | 0 |
| tool_input_accuracy | 0.615 | 8 | 5 | 0 |
| tool_output_utilization | 0.750 | 12 | 4 | 0 |
| tool_selection | 0.846 | 11 | 2 | 0 |

## Failure clusters

| Evaluator | Non-passing or incomplete results |
| --- | ---: |
| intent_resolution | 6 |
| relevance | 5 |
| task_adherence | 2 |
| task_completion | 10 |
| tool_call_accuracy | 10 |
| tool_call_success | 3 |
| tool_input_accuracy | 12 |
| tool_output_utilization | 8 |
| tool_selection | 9 |
