---
name: postgraduate-model-tier-controller
description: "Assign and audit weak, medium, and strong model tiers for Postgraduate research tasks. Use when the user asks which model is used, wants to reduce cost, configure OpenAI-compatible endpoints, benchmark tiers, or control escalation."
---

# Postgraduate Model Tier Controller

Read `../postgraduate-common/references/model-tier-policy.md` and `privacy-publication.md`.

## Assignment

- Medium: production extraction, long-paper selection, and claim review.
- No LLM: lexical/embedding retrieval.
- Strong: retrieved cross-paper synthesis and final research reasoning.
- Weak: same-paper cost benchmark only.

The paper-memory `--model-strength` option switches all ingestion calls together; it is not a per-stage router. Production runs explicitly use `medium`.

Before weak production use, compare the same complete paper and require no important knowledge, numeric, evidence, bibliography, or RAG quality loss. Escalate medium to strong only for the failed saved unit and record both attempts.

Credentials come from environment variables. Never log API keys or authorization headers.
