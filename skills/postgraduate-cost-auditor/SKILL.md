---
name: postgraduate-cost-auditor
description: "Audit Postgraduate LLM requests, token use, latency, retries, failures, and projected corpus budgets. Use when the user asks why processing is slow or expensive, wants per-paper cost, model-tier comparisons, recovery overhead, or approval before a large run."
---

# Postgraduate Cost Auditor

Read `../postgraduate-common/references/model-tier-policy.md`, `artifact-contracts.md`, and `privacy-publication.md`.

## Required Accounting

Record every actual request with paper ID, unit ID, mode, tier, resolved model, attempt, status, input/output/total tokens, input/output characters, latency, SDK retries, unit retries, and request-file pointer.

## Workflow

1. Complete one representative paper audit before a corpus run.
2. Separate clean-path cost from charged recovery overhead.
3. Report requests and tokens by task mode and paper.
4. Base projections on readable corpus size and long-paper part counts.
5. Mark projections low-confidence until a long-paper pilot exists.
6. Never hide failed provider calls from actual cost.

Do not invent monetary cost when provider pricing is unknown.
