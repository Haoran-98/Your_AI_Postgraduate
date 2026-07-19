---
name: postgraduate-knowledge-profiler
description: "Profile and visualize what a domain-specific AI postgraduate has learned from completed research. Use when the user asks what knowledge was acquired, where it is stored, wants a visual knowledge dashboard, or wants evidence-based advice about which research tasks the postgraduate is currently best prepared to perform."
---

# Postgraduate Knowledge Profiler

Read `../postgraduate-common/references/artifact-contracts.md`, `../postgraduate-common/references/evidence-policy.md`, and `references/scoring-policy.md`.

## Workflow

1. Confirm the target `Postgraduate_<EnglishDomainSlug>` vault.
2. Read `wiki/index.md`, `wiki/hot.md`, paper cards, compact paper memory, causal edges, knowledge pages, relations, and RAG manifests.
3. Run the deterministic profiler without an LLM:

```bash
python "$YOUR_AI_POSTGRADUATE_HOME/scripts/generate_postgraduate_profile.py" \
  --root "$RESEARCH_ROOT" \
  --vault Postgraduate_Example_Domain \
  --language en
```

4. Inspect the generated counts, dimension scores, top entities, ranked task fit, and explicit limitations.
5. Treat recommendations as current artifact readiness, not permanent ability, researcher quality, or evidence that a scientific idea is novel.
6. Rebuild the provider-neutral RAG corpus when the generated Markdown profile should become retrievable.

## Outputs

- `wiki/profile/postgraduate-profile.md`: Obsidian visualization and source links.
- `wiki/profile/postgraduate-profile.html`: standalone visual dashboard.
- `rag/postgraduate-profile.json`: machine-readable metrics and recommendations.

The profiler may update `wiki/index.md`, `wiki/hot.md`, and `wiki/log.md` with links to the latest profile. It must not copy raw paper text, API credentials, or private request payloads into the dashboard.

## Boundaries

- Count only artifacts that exist; never invent missing knowledge.
- Keep blocked papers visible in coverage metrics but exclude them from verified evidence.
- Preserve the distinction between exact, layout-recovered, machine-reviewed, and human-verified evidence.
- Explain every recommendation through visible dimension scores and source counts.
- Recommend research task types and domain focus, not employment, admissions, or high-stakes personal decisions.
