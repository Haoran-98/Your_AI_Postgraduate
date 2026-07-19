# Artifact Contracts

## Vault

```text
Postgraduate_<EnglishDomainSlug>/
  .obsidian/
  .raw/
  wiki/
    index.md
    hot.md
    log.md
    ideas/
    papers/
    datasets/
    variables/
    mechanisms/
    interventions/
    causal-core/
    causal-bridges/
    claims/
    hypotheses/
    gaps/
    sources/
    surveys/
    relations/semantic/
    profile/
  rag/
    postgraduate-profile.json
```

## Paper Card

Every paper card preserves paper ID, title, authors, affiliations when available, year/source, URL, DOI, citation key, BibTeX, full-text status, evidence level, causal status, and local source paths.

## Compact Paper Memory

```text
rag/paper-memory/
  papers/PXX.json
  parts/PXX/part-NNN.json
  audits/PXX.json
  requests/<run-id>.json
  usage.jsonl
  corpus.jsonl
  causal-edges.jsonl
  manifest.json
```

Each memory carries a stable ID, kind, statement, importance, evidence quote, location, source chunk IDs, evidence match type, review status, causal status, and optional directed relation.

## Provider-Neutral RAG

Each JSONL record contains a stable ID, retrieval text, content hash when available, and provenance metadata. Retrieval must be able to rehydrate the authoritative source chunk and bibliography.

## Corpus-Level Notes

Create or update variables, mechanisms, datasets/artifacts, supported claims, contrarian hypotheses/tests, causal assumptions, source expansion, survey, index, hot, and log pages.

## Postgraduate Knowledge Profile

After a substantial research pass, the profiler may create:

```text
wiki/profile/postgraduate-profile.md
wiki/profile/postgraduate-profile.html
rag/postgraduate-profile.json
```

The profile records source counts, knowledge-type counts, top entities, transparent dimension scores, ranked research-task fit, and explicit interpretation limits. It must not contain raw private request payloads or unsupported ability claims.
