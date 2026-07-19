---
name: postgraduate-bibliography-manager
description: "Add, preserve, correct, validate, and export scholarly bibliography metadata for Postgraduate paper cards. Use when the user asks for BibTeX, citation keys, authors, affiliations, DOI/URL correction, or paper-master citation consistency."
---

# Postgraduate Bibliography Manager

Read `../postgraduate-common/references/bibtex-metadata.md`, `artifact-contracts.md`, and `evidence-policy.md`.

## Rules

- Every `wiki/papers/P*.md` card keeps a YAML `bibtex: |` property.
- Prefer ACL Anthology BibTeX, arXiv BibTeX, DOI content negotiation, then paper-master fallback.
- Preserve all existing status, evidence, causal, and local-source metadata.
- Bibliography success does not imply full-text evidence.
- Correct wrong DOI/URL values consistently across the card, paper master, dataset table, and log.

```bash
python scripts/add_paper_bibtex.py --vault "$VAULT"
```

Verify card count, BibTeX count, malformed frontmatter, fallback count, and stale known-wrong identifiers.
