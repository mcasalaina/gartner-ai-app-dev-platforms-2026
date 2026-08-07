# Foundry presenter evaluation

- Agent: `bank-servicing-agent` version `22`
- Invocation: precomputed responses with trusted `x-client-demo-mode`
- Cases: 6 synthetic, read-only cases
- Eval ID: `eval_e81aab950c8f4151bc3e5f6b2c2066f3`
- Run ID: `evalrun_de6703fd416f4d86919168c9b35f35ae`
- Status: `completed`
- Result counts: {"errored": 0, "failed": 5, "passed": 1, "skipped": 0, "total": 6}
- Native rubric: `bank_servicing_rubric` version `4` (preview)
- Local hard-gate result: `failed` (14 failures)
- Report: https://ai.azure.com/nextgen/r/J7ATmha0Qr-eycbbN2gkXg,rg-aycabas-3iqs,,4iq-foundry-project-resource,4iq-foundry-project/build/evaluations/eval_e81aab950c8f4151bc3e5f6b2c2066f3/run/evalrun_de6703fd416f4d86919168c9b35f35ae

| Evaluator | Mean score | Passed | Failed | Errored |
| --- | ---: | ---: | ---: | ---: |
| bank_servicing_rubric | 0.661 | 1 | 5 | 0 |

## Rubric dimensions

| Dimension | Mean (1-5) | Applicable cases | Skipped cases |
| --- | ---: | ---: | ---: |
| account_opening_disclosures_and_esign | 3.00 | 2 | 4 |
| authorized_customer_and_service_scope | 3.83 | 6 | 0 |
| bsa_aml_cip_and_ofac_controls | 3.00 | 1 | 5 |
| customer_communication_and_record_integrity | 3.50 | 6 | 0 |
| deposit_disclosures_funds_availability_and_fdic | n/a | 0 | 6 |
| fair_treatment_fcra_and_udaap | 3.83 | 6 | 0 |
| fee_dispute_and_remediation_accuracy | n/a | 0 | 6 |
| investment_and_advisory_boundaries | 4.00 | 1 | 5 |
| privacy_glba_regulation_p | 4.33 | 3 | 3 |
| regulation_e_error_resolution | n/a | 0 | 6 |
| security_and_instruction_integrity | 4.33 | 6 | 0 |
| servicing_authority_and_human_approval | 4.00 | 1 | 5 |
| source_routing_and_evidence_provenance | 2.50 | 4 | 2 |

The standard Foundry agent-target runner cannot forward custom client headers.
This run therefore invoked the production agent first with the required trusted
mode header, then used Foundry's supported JSONL dataset-evaluation path to score
the resulting query/response pairs. No Work IQ response content was persisted in
this evaluation dataset.
