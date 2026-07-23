---
name: postgraduate-relation-builder
description: "Generate deterministic Obsidian relation maps, backlinks, semantic clusters, and paper similarity edges inside Postgraduate vaults. Use when the user asks whether knowledge is connected, wants shared methods/datasets/variables/mechanisms, or needs graph navigation regenerated."
---

# Postgraduate Relation Builder

Read `../postgraduate-common/references/vault-architecture.md`, `routing-policy.md`, and `artifact-contracts.md`.

```bash
python scripts/generate_vault_relations.py --root "$RESEARCH_ROOT"
python scripts/generate_semantic_relations.py --root "$RESEARCH_ROOT"
```

When a vault contains multiple ideas, pass `--idea-id <idea-id>` to both commands. If that idea has a paper-master CSV, only its listed paper cards enter the generated graph.

## Rules

- Generate links only within the owning domain vault.
- Keep paper membership scoped to the selected idea when a vault contains multiple research projects.
- Treat heuristic semantic clusters as navigation and triage until source-verified.
- Add compact relation sections to paper cards and knowledge pages.
- Update relation maps, index, hot, and log.
- Preserve existing user-written note content outside managed markers.
