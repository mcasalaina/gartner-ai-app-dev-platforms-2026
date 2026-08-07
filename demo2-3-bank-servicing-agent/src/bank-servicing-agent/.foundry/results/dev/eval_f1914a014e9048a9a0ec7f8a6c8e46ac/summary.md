# Foundry presenter evaluation

- Agent: `bank-servicing-agent` version `15`
- Invocation: precomputed responses with trusted `x-client-demo-mode`
- Cases: 6 synthetic, read-only cases
- Eval ID: `eval_f1914a014e9048a9a0ec7f8a6c8e46ac`
- Run ID: `evalrun_94292bc91be64704b53ad029306eea8d`
- Status: `completed`
- Result counts: {"errored": 0, "failed": 6, "passed": 0, "skipped": 0, "total": 6}
- Native rubric: `bank_servicing_rubric` version `4` (preview)
- Local hard-gate result: `failed` (16 failures)
- Report: https://ai.azure.com/nextgen/r/J7ATmha0Qr-eycbbN2gkXg,rg-aycabas-3iqs,,4iq-foundry-project-resource,4iq-foundry-project/build/evaluations/eval_f1914a014e9048a9a0ec7f8a6c8e46ac/run/evalrun_94292bc91be64704b53ad029306eea8d

| Evaluator | Mean score | Passed | Failed | Errored |
| --- | ---: | ---: | ---: | ---: |
| bank_servicing_rubric | 0.667 | 0 | 6 | 0 |

## Rubric dimensions

| Dimension | Mean (1-5) | Applicable cases | Skipped cases |
| --- | ---: | ---: | ---: |
| account_opening_disclosures_and_esign | 4.00 | 1 | 5 |
| authorized_customer_and_service_scope | 3.17 | 6 | 0 |
| bsa_aml_cip_and_ofac_controls | 4.00 | 1 | 5 |
| customer_communication_and_record_integrity | 3.67 | 6 | 0 |
| deposit_disclosures_funds_availability_and_fdic | 4.00 | 1 | 5 |
| fair_treatment_fcra_and_udaap | 3.50 | 6 | 0 |
| fee_dispute_and_remediation_accuracy | n/a | 0 | 6 |
| investment_and_advisory_boundaries | 3.00 | 1 | 5 |
| privacy_glba_regulation_p | 4.33 | 3 | 3 |
| regulation_e_error_resolution | n/a | 0 | 6 |
| security_and_instruction_integrity | 4.33 | 6 | 0 |
| servicing_authority_and_human_approval | 4.00 | 1 | 5 |
| source_routing_and_evidence_provenance | 4.00 | 3 | 3 |

The standard Foundry agent-target runner cannot forward custom client headers.
This run therefore invoked the production agent first with the required trusted
mode header, then used Foundry's supported JSONL dataset-evaluation path to score
the resulting query/response pairs. No Work IQ response content was persisted in
this evaluation dataset.
