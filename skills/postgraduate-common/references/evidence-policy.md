# Evidence Policy

## Paper States

- `fulltext-read` + `verified-fulltext`: readable full text supports paper knowledge.
- `fulltext-blocked` + `blocked`: retain bibliography and relevance notes only.
- Metadata, abstracts, snippets, and search summaries never support verified claims.

## Memory Evidence

- `exact`: evidence quote is a contiguous normalized match in the cited raw chunk.
- `layout-recovered`: deterministic ordered-token recovery handles multi-column extraction artifacts; it must still receive claim-support review.
- `unmatched`: reject from validated memory.
- `machine-reviewed`: a model checked the complete statement against the original chunk.
- `human-verified`: a human checked the source and location.

Machine validation is not human verification.

## Causal Language

- Use `reported_association` for observed relationships.
- Use `author_causal_claim` when authors make causal wording without full identification.
- Use `identified_causal_effect` only when the design supports identification.
- Use `mechanistic_hypothesis` for proposed pathways.
- Emit a directed edge only when its source memory is validated.
