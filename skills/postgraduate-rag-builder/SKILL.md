---
name: postgraduate-rag-builder
description: "Build provider-neutral RAG corpora and compact memory indexes from Postgraduate vaults. Use when the user asks to convert Markdown/full text into JSONL, create retrieval metadata, filter blocked evidence, combine vault corpora, or prepare data for external vector databases."
---

# Postgraduate RAG Builder

Read `../postgraduate-common/references/artifact-contracts.md` and `evidence-policy.md`.

```bash
python scripts/prepare_rag_corpus.py --root "$RESEARCH_ROOT"
```

## Policy

- Give every record a stable ID, retrieval text, provenance, source type, evidence level, and review status.
- Keep blocked records out of evidence retrieval.
- Treat machine and derived synthesis as navigation unless reviewed.
- Keep compact paper memory as the default durable recall layer.
- Store bibliography once per paper and reference it from memories.
- Preserve source chunk IDs so retrieval can rehydrate original evidence.
- Keep JSONL independent of any specific vector database.
- For multi-project vaults, record all `idea_ids` and use a vault-level RAG note instead of assigning shared retrieval data to the first idea.
