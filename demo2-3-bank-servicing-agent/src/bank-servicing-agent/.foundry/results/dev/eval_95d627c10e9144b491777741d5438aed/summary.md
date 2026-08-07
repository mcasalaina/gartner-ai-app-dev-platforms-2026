# Foundry presenter evaluation

- Agent: `bank-servicing-agent` version `15`
- Invocation: precomputed responses with trusted `x-client-demo-mode`
- Cases: 6 synthetic, read-only cases
- Eval ID: `eval_95d627c10e9144b491777741d5438aed`
- Run ID: `evalrun_ba524093e3af45c5a25fab8f5dd67855`
- Status: `completed`
- Result counts: {"errored": 0, "failed": 4, "passed": 2, "skipped": 0, "total": 6}
- Custom rubric: `bank_servicing_rubric` version `2` (preview)
- Report: https://ai.azure.com/nextgen/r/J7ATmha0Qr-eycbbN2gkXg,rg-aycabas-3iqs,,4iq-foundry-project-resource,4iq-foundry-project/build/evaluations/eval_95d627c10e9144b491777741d5438aed/run/evalrun_ba524093e3af45c5a25fab8f5dd67855

| Evaluator | Mean score | Passed | Failed | Errored |
| --- | ---: | ---: | ---: | ---: |
| bank_servicing_rubric | 0.731 | 2 | 4 | 0 |

## Rubric dimensions

| Dimension | Mean (1-5) | Applicable cases | Skipped cases |
| --- | ---: | ---: | ---: |
| account_and_investment_accuracy | 4.00 | 3 | 3 |
| authoritative_source_routing | 3.40 | 5 | 1 |
| bank_domain_adherence | 4.00 | 6 | 0 |
| format_length_and_relevance | 3.67 | 6 | 0 |
| general_quality_and_voice_clarity | 4.00 | 6 | 0 |
| hitl_publishing_integrity | 4.33 | 3 | 3 |
| kyc_confirmation_and_write_safety | 5.00 | 2 | 4 |
| multi_turn_context_continuity | 3.83 | 6 | 0 |
| pdf_grounding_and_citations | 3.00 | 1 | 5 |
| prompt_injection_resistance | 4.33 | 3 | 3 |
| salary_dlp_enforcement | 4.67 | 3 | 3 |
| service_media_alignment | n/a | 0 | 6 |
| user_data_isolation | 4.00 | 4 | 2 |

The standard Foundry agent-target runner cannot forward custom client headers.
This run therefore invoked the production agent first with the required trusted
mode header, then used Foundry's supported JSONL dataset-evaluation path to score
the resulting query/response pairs. No Work IQ response content was persisted in
this evaluation dataset.
