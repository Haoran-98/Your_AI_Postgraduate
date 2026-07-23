---
name: postgraduate-domain-router
description: "Assign every new research task to a suitable existing Postgraduate researcher or create a new independent domain vault when none fits. Use when starting a research idea, deciding which researcher owns it, checking current task fit, normalizing Chinese domain wording to an English vault slug, or preventing a poor cross-domain assignment."
---

# Postgraduate Domain Router

Read `../postgraduate-common/references/governance.md`, `routing-policy.md`, `researcher-assignment-policy.md`, and `idea-batch-ingestion.md`.

## Workflow

1. Reduce the idea to its core object, population, mechanism, and research objective.
2. Inventory existing `Postgraduate_*` vaults and inspect plausible candidates' profiles, index, hot cache, and direct RAG matches.
3. Reuse a postgraduate only when both domain ownership and directly transferable stored knowledge are present.
4. Prefer Education, Military, Information_Opinion, or Mental_Health when one passes the assignment gate.
5. Create a new English domain slug when no existing vault passes; generic method overlap alone is insufficient.
6. Write `wiki/meta/<idea-id>-postgraduate-assignment.md` before downstream research begins.
7. Output the selected `Postgraduate_<EnglishDomainSlug>`, evidence, reuse boundaries, and rationale.
8. Never merge unrelated ideas into a broad global vault.

Chinese text may remain in note content, but generated paths use English ASCII slugs.
