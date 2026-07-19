# Deep Full-Text Causal Research Subskill

Use this subskill when the user asks for strict deep literature reading, full-text paper extraction, causal knowledge-base conversion, evidence-backed idea support/refutation, or large paper-corpus research inside a `Postgraduate_*` vault.

## Non-Negotiable Evidence Rule

- Do not convert metadata, abstracts, snippets, or search-result summaries into verified paper knowledge.
- A paper card must be either:
  - `status: fulltext-read` and `evidence_level: verified-fulltext`, or
  - `status: fulltext-blocked` and `evidence_level: blocked` with a concrete reason.
- Blocked papers may keep bibliography metadata and relevance notes, but they must not support verified claims.
- Preserve raw files in `.raw/`; synthesize into `wiki/`.
- Never delete or replace paper-card bibliography metadata, authors, affiliations, venue/source, URL, DOI, citation key, or BibTeX when building derived memory or RAG layers.

## Compact Long-Term Memory

Use compact paper memory as the default machine recall layer instead of exhaustive per-chunk graph expansion:

- keep paper cards, paper masters, PDFs, full text, and BibTeX as the authoritative literature layer;
- retain a small set of important research questions, contributions, variables, datasets, experiments, findings, limitations, mechanisms, causal claims, contradictions, transferable principles, and open questions;
- attach every evidence memory to a quote, location, and original source chunk; mark it `exact` only for a contiguous raw-text match, otherwise require deterministic `layout-recovered` validation plus claim-support review;
- store bibliography once per paper and reference it from memory records instead of repeating BibTeX on every fact;
- use deterministic quote validation followed by compact claim-support review;
- for long papers, evidence-filter part candidates before consolidation and let the model select immutable candidate IDs only; never let consolidation rewrite statements, quotes, locations, or relations;
- emit causal edges only when the source supports them and link each edge to a validated memory ID;
- retrieve compact memories first, expand causal links second, and rehydrate raw source chunks before final reasoning;
- generate idea-specific support/refutation at query time rather than repeating it during every paper ingestion.

For the current workspace, use:

```bash
.venv-hyperextract/bin/python "$YOUR_AI_POSTGRADUATE_HOME/scripts/run_paper_memory_pipeline.py" \
  --root "$RESEARCH_ROOT" \
  --vault Postgraduate_Example_Domain \
  --paper-id P02 \
  --model-strength medium

.venv-hyperextract/bin/python "$YOUR_AI_POSTGRADUATE_HOME/scripts/query_paper_memory_rag.py" \
  Postgraduate_Example_Domain \
  --root "$RESEARCH_ROOT" \
  "research question"
```

Normal papers use one compact extraction and one claim-support review. Long papers must use independently saved parts plus one paper-level consolidation. Pilot at least one long paper before approving an unrestricted corpus run.

## Model Tier Policy

Use task-based model tiers for compact paper memory. This policy is mandatory unless the user explicitly requests a controlled model comparison:

| Task | Model tier | Rule |
| --- | --- | --- |
| Important-knowledge extraction | `medium` | Default for normal papers and every independently saved long-paper part. |
| Long-paper candidate selection and profile consolidation | `medium` | Select immutable candidate IDs; never let consolidation rewrite evidence quotes or locations. |
| Claim-support and causal-language review | `medium` | Review validated exact or deterministic layout-recovered evidence against original chunks. |
| Lexical or embedding retrieval | no LLM | Retrieve compact memories, causal links, source chunks, and bibliography without a generation call. |
| Cross-paper synthesis, idea support/refutation, and research reasoning | `strong` | Use only after retrieval has assembled source-grounded evidence; enable through the query tool's `--chat` mode. |
| Cost experiment | `weak` | Disabled by default. Use only on a small same-paper benchmark and never for an unrestricted corpus run before passing the gates below. |

The compact paper-memory pipeline's `--model-strength` option switches all ingestion requests together. It is not a per-stage router. Therefore, production ingestion must explicitly use `--model-strength medium`; do not pass `weak` as a shortcut for task-tier routing.

The older exhaustive Hyper-Extract workflow may retain its legacy `weak` one-stage extraction plus `medium` review configuration for audit and historical comparison. Do not transfer that legacy split to compact paper memory without a new same-input benchmark.

Before allowing `weak` for any production ingestion, compare weak and medium on the same complete paper and require all of the following:

- no timeout, malformed structured output, or hidden retry;
- all required core knowledge types present when supported by the paper;
- no loss of important numeric findings, sample sizes, effect sizes, datasets, experimental conditions, or limitations;
- exact and deterministic layout-recovered evidence validation followed by claim-support review;
- bibliography, authors, affiliations, URL, DOI, citation key, and BibTeX preserved;
- materially lower total tokens without a meaningful reduction in validated-memory recall or RAG answer quality.

Use `strong` during ingestion only for a documented exception after medium fails on the same independently saved unit. Retry only that unit, record the escalation, and include both attempts in actual cost.

For every batch, record at least `paper_id`, task mode, requested model tier, resolved model ID, request count, input/output/total tokens, elapsed time, SDK retries, unit retries, validation counts, and any tier escalation. Never write API keys or authorization headers to request logs or the vault.

## Per-Paper Required Extraction

For every readable paper, extract at least:

- research question,
- method,
- variables and constructs,
- dataset/corpus/artifacts,
- experimental design,
- main findings,
- limitations/threats,
- causal interpretation,
- transferable mechanism,
- support for the user's idea,
- counterevidence/risk against the idea,
- contrarian hypothesis,
- experiment to verify or falsify.

When the card already has a concise schema, add a paper-specific section such as:

```markdown
## Deep Full-Text Causal Extraction
- Paper-specific treatment:
- Mechanism for the idea:
- Support point:
- Refutation/risk point:
- Transferable design:
- Verification experiment:
```

## Corpus-Level Products

After individual papers, update or create durable pages:

- `wiki/evidence/idea-XX-fulltext-reading-plan.md`
- `wiki/variables/idea-XX-variables.md`
- `wiki/mechanisms/idea-XX-mechanisms.md`
- `wiki/datasets/idea-XX-datasets-and-artifacts.md`
- `wiki/claims/idea-XX-supported-claims.md`
- `wiki/hypotheses/idea-XX-contrarian-hypotheses-and-tests.md`
- causal assumption notes under `wiki/causal-core/assumptions/`
- source/cross-venue expansion notes under `wiki/sources/`
- `wiki/hot.md`, `wiki/log.md`, and `wiki/index.md`

## Cross-Venue Expansion

When a paper naturally points to current top-venue work, search and record official sources from ACL, EMNLP, NAACL, COLING, NeurIPS, ICLR, ICML, IJCAI, AIED, EDM, LAK, CHI, CSCW, UIST, SIGCSE, Learning@Scale, and credible publisher/project pages.

For each external paper, record:

- venue/year,
- official link,
- triggering corpus paper,
- why it matters,
- evidence level (`official-page-verified`, `external-linkage`, or `fulltext-read`),
- directional implication: supports, refutes, or complicates the idea.

External linkages generate hypotheses and search routes; they are not verified causal evidence until full text is read.

## Completion Checks

Run checks before reporting completion:

```bash
rg -n "status: screened|\\| partial \\||\\| pending \\|" "$VAULT/wiki" || true
rg -n "status: fulltext-read" "$VAULT/wiki/papers/P*.md" | wc -l
rg -n "status: fulltext-blocked" "$VAULT/wiki/papers/P*.md" | wc -l
rg -n "causal_status: causal-integrated" "$VAULT/wiki/papers/P*.md" | wc -l
rg -n "causal_status: blocked" "$VAULT/wiki/papers/P*.md" | wc -l
find "$VAULT" -print | LC_ALL=C grep '[^ -~]' || true
ps -eo pid,ppid,stat,etime,cmd | rg 'curl|pdftotext|ocr|generate_vault_relations|generate_semantic_relations' || true
```

Regenerate relation and semantic layers after meaningful changes:

```bash
python "$YOUR_AI_POSTGRADUATE_HOME/scripts/generate_vault_relations.py" --root "$ROOT" --date YYYY-MM-DD
python "$YOUR_AI_POSTGRADUATE_HOME/scripts/generate_semantic_relations.py" --root "$ROOT" --date YYYY-MM-DD
```
