---
name: postgraduate-hyperextract-adapter
description: "Use Hyper-Extract as the optional lower-level exhaustive paper graph extractor beneath Postgraduate evidence governance. Use when the user asks for exhaustive node/edge extraction, graph indexing, validated Hyper-Extract artifacts, legacy comparison, or MCP-compatible graph access."
---

# Postgraduate Hyper-Extract Adapter

Read `../postgraduate-common/references/evidence-policy.md`, `model-tier-policy.md`, and `current-method-inventory.md`.

Compact paper memory remains the default recall layer. Hyper-Extract is optional for exhaustive graph inspection and comparison.

## Safe Workflow

1. Build the provider-neutral RAG corpus.
2. Run one API request at a time.
3. Save each source unit atomically.
4. Use one-stage node-and-edge extraction; review only priority method/experiment/result/limitation units.
5. Disable SDK and automatic unit retries.
6. Use deterministic duplicate merging.
7. Audit one full paper before any corpus run.
8. Sanitize the graph by source validation before RAG use.

```bash
python scripts/run_hyperextract_pipeline.py --root "$RESEARCH_ROOT" --vault Postgraduate_Example_Domain --dry-run
```

Raw graphs remain machine-extracted. Only validated graph artifacts may enter validated retrieval.
