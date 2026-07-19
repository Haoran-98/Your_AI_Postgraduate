# IDEA Batch Ingestion Standard

Use this when the user asks to ingest one or more IDEA markdown files into the AutoResearch knowledge base.

## Defaults

- Default root: `$HOME/auto-research`.
- Standard first-choice directions use English vault slugs:
  - `Education`
  - `Military`
  - `Information_Opinion`
  - `Mental_Health`
- If an idea does not fit these four directions, create a new `Postgraduate_<EnglishDomainSlug>` vault. Do not force a weak classification.
- Each vault must be Obsidian-ready: `.obsidian/`, `.raw/`, and `wiki/` are required.
- Obsidian desktop is optional. The agent writes standard Markdown vault files directly.
- All generated folder and file names must be English ASCII slugs. Chinese text may appear in note content, but not in generated paths.

## Required Plan Before Batch Work

Before ingesting a new IDEA file, list:

```text
Input file:
Output root:
Idea count:
Domain routing table:
New domains to create:
Smoke-test target:
Research depth:
```

Wait for user confirmation if they explicitly ask to inspect the plan first.

## Routing Rules

Use the core meaning of the idea:

- `Education`: classroom, teachers, students, learning groups, educational cognition, academic training.
- `Military`: battlefield, combat planning, military agents, operational strategy, wartime cognition.
- `Information_Opinion`: media, public opinion, propaganda, online discourse, misinformation, author profiling.
- `Mental_Health`: cognitive decline, mental state, behavior simulation, stress, affect, human cognitive health.

Create a new domain when the idea is mainly about cross-domain infrastructure or another topic not owned by the four directions.

## File Layout Per Idea

For each idea, create or update:

```text
Postgraduate_<EnglishDomainSlug>/
  .raw/idea-XX-<slug>.md
  wiki/ideas/idea-XX-<slug>.md
  wiki/index.md
  wiki/hot.md
  wiki/log.md
```

After literature research, also populate as applicable:

```text
wiki/papers/
wiki/datasets/
wiki/mechanisms/
wiki/variables/
wiki/causal-bridges/
wiki/gaps/
wiki/surveys/
```

## Idea Note Minimum Content

```markdown
---
type: idea
domain: <domain>
status: seed | researched | partial
updated: YYYY-MM-DD
idea_id: idea-XX
---

# <idea title>

## Seed

## Public Search Keywords

## Knowledge Slots

## Literature Map

## Dataset / Benchmark Candidates

## Opportunity Gaps

## Next Research Tasks
```

Do not paste private or unpublished text into public searches. Convert each idea into public-safe keywords first.

## Smoke Test

A smoke test should use exactly one idea and verify:

1. The target `Postgraduate_<domain>` vault exists.
2. `.obsidian/app.json`, `.obsidian/core-plugins.json`, and `.obsidian/workspace.json` exist.
3. `.raw/idea-XX-<slug>.md` exists.
4. `wiki/ideas/idea-XX-<slug>.md` exists.
5. `wiki/index.md`, `wiki/hot.md`, and `wiki/log.md` reference the ingested idea.

Do not run full literature research during a smoke test unless the user asks for it.
