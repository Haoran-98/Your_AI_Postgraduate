---
name: postgraduate-rag-reasoner
description: "Retrieve Postgraduate paper memories and reason across source-grounded evidence. Use when the user asks a research question, wants knowledge transfer across papers, support/refutation for an idea, causal connections, contrarian hypotheses, experiment suggestions, or citation-ready synthesis."
---

# Postgraduate RAG Reasoner

Read `../postgraduate-common/references/evidence-policy.md`, `model-tier-policy.md`, and `artifact-contracts.md`.

## Retrieval Order

1. Retrieve compact memories without an LLM.
2. Expand relevant directed evidence edges.
3. Rehydrate original source chunks.
4. Attach bibliography, citation key, URL, DOI, and BibTeX.
5. Use the strong model only for final cross-paper synthesis when requested.

```bash
python scripts/query_paper_memory_rag.py \
  Postgraduate_Example_Domain \
  "research question" \
  --root "$RESEARCH_ROOT"
```

Add `--chat` for strong-model synthesis. Cite paper IDs and memory IDs, distinguish support from complication/refutation, and keep causal conclusions within study-design limits.
