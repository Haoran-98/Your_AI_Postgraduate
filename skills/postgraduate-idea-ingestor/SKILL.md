---
name: postgraduate-idea-ingestor
description: "Ingest one or more IDEA markdown files into Postgraduate vaults. Use when the user asks to batch import research ideas, create raw and durable idea notes, route multiple ideas, or run an IDEA ingestion smoke test."
---

# Postgraduate Idea Ingestor

Read `../postgraduate-common/references/idea-batch-ingestion.md`, `obsidian-writing.md`, and `governance.md`.

## Workflow

1. Record input file, output root, idea count, routing table, new domains, smoke-test target, and requested depth.
2. Route each idea with `postgraduate-domain-router`.
3. Preserve the source under `.raw/idea-XX-<slug>.md`.
4. Register or update the assigned project under `wiki/research-lines/`.
5. Create `wiki/ideas/idea-XX-<slug>.md` with seed, public search keywords, knowledge slots, literature map, dataset candidates, gaps, and next tasks.
6. Update index, hot, and log pages.
7. For a smoke test, verify exactly one idea without starting full literature research unless requested.

Convert private idea details into public-safe keywords before web search.
