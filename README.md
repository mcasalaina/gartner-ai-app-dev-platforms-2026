# Microsoft Submission — Gartner Magic Quadrant for AI Application Development Platforms 2026

This repository contains Microsoft's demo submissions for the **Gartner Magic Quadrant and Critical Capabilities for AI Application Development Platforms 2026** evaluation.

## Submission Deadline

**24 August 2026, 11:59 PM PST** — submitted via the Gartner Provider Information Portal.

## Scenario

All demos are built around the following scenario:

> You are the owner of an investment bank offering retail and commercial services (checking/savings, retirement, investments) operating in the US, European, and Chinese markets. The bank is located near the **Texas Stock Exchange (TXSE)** in Dallas, Texas and also uses NYSE, Nasdaq, and major European exchanges.

The driving problem statement is to build AI applications that help design and operate this bank — including KYC, account management, fraud detection, investment services, marketing, and regulatory compliance.

---

## Demos

The four demos below correspond directly to the scenarios requested in the PDF: *Demo Instructions — Gartner AI App Dev Platforms MQ 2026.pdf*.

### Demo 1 — Deep Research Agent

Build an AI deep research agent using an agentic framework that:

- Accepts the bank strategy problem statement as input
- Uses an LLM to optimize, refine, and decompose the query into sub-questions
- Generates a structured research plan (objectives, methods, evaluation criteria)
- Leverages tool calling / MCP (e.g., web search APIs) for information gathering
- Uses multi-agent collaboration for parallel processing across research sections
- Includes a human-in-the-loop review and refinement step
- Incorporates multimodal input (data/charts) and output (graphics/logos)
- Combines all sections into a comprehensive final report with citations, exported as a PDF
- Generates one highlighted chapter (services list) combining text, images, and speech

**Platform capabilities demonstrated:** IDE/low-code/high-code/graphical development, model catalog, testing/validation, data preparation, tracing, evaluation, debugging, agent operations, observability, deployment, orchestration, cost management, and control processes.

---

### Demo 2 — External Customer AI Assistant

Build an AI assistant grounded in the research output from Demo 1 for external bank customers, enabling:

- Retrieval of detailed service information (text + images)
- AI-generated service images
- Speech output for account and investment tracking

**Platform capabilities demonstrated:**
- Automatic quality control (format, length, relevance filtering)
- Human-in-the-loop review for updating service descriptions
- A/B testing across multiple models
- Continuous feedback loop from the AI application

---

### Demo 3 — Bank Customer AI Agent

Build an AI agent that helps bank customers open an account and access services, demonstrating:

- Grounding via both context/prompt engineering and RAG, verified against the PDF from Demo 1
- Guardrails preventing responses to non-bank requests
- Data-leak prevention (DLP) triggered by salary-related queries
- Out-of-the-box metrics reporting: comprehensiveness, accuracy, response time, costs

---

### Demo 4 — Avatar / Digital Human

Build a photorealistic multilingual avatar for bank marketing and promotion that:

- Is grounded in the text and images from Demo 2
- Accepts audio/speech input and responds in multiple languages and voice tones
- Displays or references menu items / services being discussed
- Adapts responses based on customer questions
- Demonstrates effective guardrails when asked out-of-scope questions

---

## Deliverables Per Demo

For each demo, the following artifacts are provided:

1. **Source code** — inspectable in an IDE or design studio
2. **Runtime executable** — packaged in containers or Helm charts for on-premises or cloud deployment
3. **Build instructions** — CLI, automation scripts, or CI/CD pipeline to compile and deploy

---

## Repository Structure

```
.
├── README.md
├── Demo Instructions - Gartner AI App Dev Platforms MQ 2026.pdf
├── demo1-deep-research-agent/
├── demo2-customer-ai-assistant/
├── demo3-bank-customer-agent/
└── demo4-avatar-digital-human/
```

---

## Table of Contents (Video Timecodes)

A separate `table-of-contents.md` file with timecodes `[MM:SS]` for each use case and differentiating capability will be included with the final video submission.

---

*All information in this repository is confidential and intended solely for the Gartner MQ evaluation process.*
