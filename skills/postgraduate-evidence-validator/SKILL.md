---
name: postgraduate-evidence-validator
description: "Validate paper-memory and Hyper-Extract evidence against original source chunks. Use when the user asks to audit quotes, reject unsupported claims, distinguish exact/layout-recovered evidence, sanitize a graph, or check causal wording and source provenance."
---

# Postgraduate Evidence Validator

Read `../postgraduate-common/references/evidence-policy.md` and `artifact-contracts.md`.

## Validation Order

1. Resolve the cited source chunk from the location.
2. Accept `exact` only for a contiguous normalized match.
3. Use deterministic ordered-token `layout-recovered` matching only for PDF multi-column artifacts.
4. Reject unmatched evidence.
5. Run claim-support review against the complete original chunk.
6. Narrow composite statements or reject them when numbers, scope, comparison, or causal wording are unsupported.
7. Emit directed edges only from validated memories.

```bash
python scripts/validate_hyperextract_evidence.py "$VAULT"
python scripts/sanitize_hyperextract_graph.py "$VAULT"
```

Machine-validated is never reported as human-verified.
