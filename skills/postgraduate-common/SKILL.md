---
name: postgraduate-common
description: "Maintain and audit shared governance for the Your AI Postgraduate skill family, including naming, evidence levels, artifact contracts, privacy, model tiers, and parent-child routing. Use for skill-system maintenance rather than ordinary research execution."
---

# Postgraduate Common

Own shared contracts for the skill family. Child skills must reference these files instead of inventing parallel policies.

## Shared References

- `references/governance.md`: vault ownership, naming, source handling, and update rules.
- `references/artifact-contracts.md`: durable folder, note, RAG, memory, and audit outputs.
- `references/evidence-policy.md`: full-text, blocked, exact, layout-recovered, machine-reviewed, and human-verified states.
- `references/model-tier-policy.md`: weak, medium, strong, retrieval, escalation, and logging rules.
- `references/privacy-publication.md`: private-source and public-repository boundaries.
- `references/current-method-inventory.md`: existing methods only; use to prevent scope invention.
- Existing extracted references in this directory cover AutoResearch, BibTeX, full-text research, IDEA ingestion, Obsidian writing, routing, and vault architecture.

## Maintenance Rule

When changing a shared contract, update the common reference first, then inspect every child Skill that depends on it. Keep all committed examples free of usernames and absolute machine paths.
