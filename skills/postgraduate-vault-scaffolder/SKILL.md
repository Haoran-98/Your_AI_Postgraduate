---
name: postgraduate-vault-scaffolder
description: "Create and initialize Obsidian-ready Postgraduate research vaults. Use when the user asks to set up a domain researcher, create the required .obsidian/.raw/wiki structure, seed index/hot/log pages, or validate vault readiness."
---

# Postgraduate Vault Scaffolder

Read `../postgraduate-common/references/vault-architecture.md` and `artifact-contracts.md`.

Use the existing deterministic script:

```bash
python scripts/scaffold_postgraduate_vault.py \
  --root "$RESEARCH_ROOT" \
  --domain "Example Domain"
```

## Checks

- Vault name follows `Postgraduate_<EnglishDomainSlug>`.
- `.obsidian/app.json`, `core-plugins.json`, and `workspace.json` exist.
- `.raw/` and all required `wiki/` role folders exist.
- `wiki/index.md`, `wiki/hot.md`, and `wiki/log.md` exist.
- Existing files are preserved.
