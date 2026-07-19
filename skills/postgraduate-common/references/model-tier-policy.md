# Model Tier Policy

| Task | Tier |
| --- | --- |
| Paper extraction | medium |
| Long-paper candidate selection/profile consolidation | medium |
| Claim-support review | medium |
| Lexical or embedding retrieval | no LLM |
| Cross-paper synthesis and research reasoning | strong |
| Controlled cost experiment | weak |

Weak is disabled for production ingestion until a same-paper benchmark preserves core knowledge, important numbers, evidence validation, bibliography, and RAG answer quality without timeout or hidden retries.

Use strong during ingestion only after medium fails on the same independently saved unit. Retry only that unit and include every attempt in actual cost.

Log paper ID, task mode, requested tier, resolved model ID, request count, input/output/total tokens, elapsed time, SDK retries, unit retries, and escalation.
