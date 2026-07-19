# Knowledge Profile Scoring Policy

The profile is a deterministic readiness summary over existing vault artifacts. It is not an LLM judgment and does not measure intelligence, novelty, or future potential.

## Knowledge Sources

| Source | What it represents |
| --- | --- |
| `wiki/papers/P*.md` | Bibliography, paper status, full-text evidence state, and deep-reading cards |
| `rag/paper-memory/papers/P*.json` | Compact validated findings, methods, variables, datasets, experiments, limitations, mechanisms, and open questions |
| `rag/paper-memory/causal-edges.jsonl` | Validated directed relations derived from paper memory |
| `wiki/variables`, `mechanisms`, `claims`, `hypotheses`, `causal-*`, `surveys` | Corpus-level synthesis and causal knowledge |
| `wiki/relations` | Navigable deterministic and semantic relations |
| `rag/corpus.jsonl` and `rag/paper-memory/corpus.jsonl` | Retrieval-ready source and memory records |

## Dimensions

All dimensions are scored from 0 to 100 with visible saturation targets:

- **Literature foundation**: paper volume, verified-fulltext coverage, paper-memory coverage, and venue diversity.
- **Evidence grounding**: machine/human review ratio, exact or layout-recovered match ratio, validated-memory volume, and non-blocked coverage.
- **Method and empirical knowledge**: coverage of study-design, experiment, dataset, variable, finding, and limitation memories plus durable dataset/experiment pages.
- **Causal reasoning**: causal-status memories, validated causal edges, mechanism/variable memories, and causal knowledge pages.
- **Synthesis and innovation**: transferable principles, contradictions, open questions, surveys, claims, hypotheses, gaps, bridges, and relation pages.
- **Retrieval readiness**: source RAG records, compact-memory records, paper-memory coverage, and relation pages.

Every target is a reporting threshold, not a scientific quality standard. More files do not automatically imply better research.

## Task Fit

Rank these current task types through fixed weighted combinations of the dimensions:

- evidence-grounded RAG research;
- knowledge-graph curation;
- literature synthesis and survey writing;
- causal mechanism and hypothesis development;
- experiment and evaluation design;
- dataset and benchmark construction.

Use `ready now` only when the task score and its core dimension are both at least 80. Use `suitable with targeted review` for scores from 60 upward when that gate is not met, and `needs more evidence` below 60. The core dimensions are retrieval readiness for RAG, causal reasoning for graph/causal work, literature foundation for survey work, and method/empirical knowledge for experiment or dataset work. Always show the contributing dimensions and the lowest-scoring capability gap.

## Interpretation

The highest-ranked task is the best-supported use of the current stored knowledge. It does not prove that the postgraduate can complete the task autonomously. Human review remains required for research claims, experiment feasibility, novelty, ethics, and publication decisions.
