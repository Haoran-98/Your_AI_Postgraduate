---
name: postgraduate-paper-memory
description: "Build compact, source-grounded long-term paper memory for RAG. Use when the user asks to remember important knowledge from full papers, process a paper corpus, split long papers, preserve bibliography, resume failed parts, or reduce token use compared with exhaustive graphs."
---

# Postgraduate Paper Memory

Read `../postgraduate-common/references/deep-fulltext-causal-research-subskill.md`, `artifact-contracts.md`, `evidence-policy.md`, and `model-tier-policy.md`.

## Production Policy

- Use `medium` for extraction, long-paper selection, and claim review.
- Keep at most a compact set of important durable memories per paper.
- Save long-paper parts independently at about 70,000 source characters.
- Evidence-filter candidates before consolidation.
- Consolidation selects immutable candidate IDs and cannot rewrite evidence.
- Retry only failed parts; preserve every charged request in cost totals.
- Preserve paper cards, masters, PDFs, text, authors, affiliations, URL, DOI, citation key, and BibTeX.

```bash
python scripts/run_paper_memory_pipeline.py \
  --root "$RESEARCH_ROOT" \
  --vault Postgraduate_Example_Domain \
  --paper-id P01 \
  --model-strength medium
```

Use `--rebuild-from-parts` for downstream quality repair without repeating extraction.
