---
name: your-ai-postgraduate
description: "Orchestrate the complete Your AI Postgraduate research system. Use when the user asks to start, plan, continue, inspect, or complete a multi-stage research project spanning ideas, literature, full text, paper memory, causal knowledge, RAG, knowledge visualization, task-fit profiling, cost control, quality gates, and Git synchronization."
---

# Your AI Postgraduate

Treat each `Postgraduate_<EnglishDomainSlug>` vault as one domain-specific postgraduate researcher. Route work to child skills; do not perform every stage in the parent context.

## Start

1. Read `../postgraduate-common/references/governance.md` and `references/routing-table.md`.
2. For every new research task, apply `../postgraduate-common/references/researcher-assignment-policy.md` through `postgraduate-domain-router` before selecting a vault.
3. Record the decision in `wiki/meta/<idea-id>-postgraduate-assignment.md`; reuse only when domain ownership and direct transferable knowledge both exist, then register the project under `wiki/research-lines/`.
4. Identify the target vault, current stage, requested depth, source permissions, model/API availability, and persistence requirement.
5. Read the target vault's `wiki/index.md` and `wiki/hot.md` when they exist.
6. Route only to the child skills needed for the current task.
7. Enforce stage gates before advancing.

## Stage Order

1. Audit existing postgraduate fit, assign the task, and create a vault only when none fits.
2. Ingest the idea and create durable notes.
3. Search and screen literature.
4. Acquire lawful full text and bibliography.
5. Perform strict full-text reading.
6. Build compact paper memory and validate evidence.
7. Synthesize variables, mechanisms, datasets, claims, hypotheses, and causal bridges.
8. Build relations and RAG artifacts.
9. Retrieve evidence and reason about research ideas.
10. Visualize acquired knowledge and profile current research-task fit.
11. Audit quality, cost, and repository state; then synchronize Git.

Do not force every request through every stage. Resume from durable artifacts already present.

## Non-Negotiable Gates

- Metadata or abstracts never become verified full-text evidence.
- Blocked papers retain bibliography but do not support verified claims.
- Raw sources remain immutable under `.raw/`.
- Paper memory preserves authors, affiliations, venue/source, URL, DOI, citation key, and BibTeX.
- Causal wording stays conservative unless the study design identifies a causal effect.
- Medium handles production ingestion; strong handles retrieved cross-paper synthesis; weak remains benchmark-only.
- Every model call is auditable by paper, task, model tier, token count, latency, and retry state.
- Knowledge profiles reflect current stored artifacts and gaps; they do not measure permanent ability or scientific novelty.
- Public repositories exclude credentials, private ideas, copyrighted corpora, PDFs without redistribution rights, and machine-specific paths.
- Every new research task has a durable postgraduate-assignment note before literature work begins.

## References

- `references/routing-table.md`: child-skill selection.
- `references/system-workflow.md`: complete workflow and handoffs.
- `../postgraduate-common/references/artifact-contracts.md`: required files and schemas.
- `../postgraduate-common/references/evidence-policy.md`: evidence status and causal boundaries.
- `../postgraduate-common/references/current-method-inventory.md`: methods already present in this system.
