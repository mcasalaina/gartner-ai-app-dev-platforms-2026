# Bank service content

This folder defines the reviewed source inputs and publishing contracts for the
Demo 1-derived service corpus.

- The source PDF is
  `../demo1-deep-research-agent/examples/generated-bank-strategy/bank-strategy-report.pdf`.
- Extracted text and image metadata are staged, quality checked, and reviewed.
- Only approved immutable versions are published to a **separate** Demo 1
  service corpus target. The existing bank policy Foundry IQ connection
  `kb-acme-bank-foundryiq` remains read-only for policy retrieval.
- Generated images are synthetic service imagery and must include provenance,
  prompt hash, model deployment, reviewer, and approval timestamp.
- Schemas live in `schemas/`, representative synthetic reviewed-content manifests
  live in `seeds/`, and focused validation tests live in `tests/`.

Runtime content and generated media belong in Azure Storage, not in Git.
