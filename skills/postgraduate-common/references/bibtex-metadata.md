# BibTeX Metadata For Paper Cards

Use this reference when a domain vault has paper cards, paper-master CSV files, or the user asks to add, update, export, or verify BibTeX metadata.

## Contract

- Every `wiki/papers/P*.md` paper card should have a YAML frontmatter property:

```yaml
bibtex: |
  @article{...}
```

- Prefer official BibTeX sources in this order:
  1. ACL Anthology `.bib` when the URL or DOI identifies an ACL paper.
  2. arXiv `https://arxiv.org/bibtex/<id>` for arXiv records.
  3. DOI content negotiation with `Accept: application/x-bibtex`.
  4. Local paper-master fallback only when all official sources fail.

- Preserve existing `status`, `evidence_level`, `causal_status`, `local_text`, and other paper metadata.
- Do not treat a successful BibTeX lookup as full-text evidence. Blocked papers may still have BibTeX metadata.
- If a DOI in paper-master is discovered to be wrong, correct the paper card, paper-master CSV/Markdown, datasets/artifacts tables, and log the correction.
- After batch updates, verify:
  - number of `bibtex: |` fields equals number of `P*.md` cards,
  - no malformed frontmatter,
  - fallback count is reported,
  - no stale known-wrong DOI remains in wiki pages unless it appears only in a correction log.

## Script

Use `scripts/add_paper_bibtex.py` for deterministic batch updates:

```bash
python "$YOUR_AI_POSTGRADUATE_HOME/scripts/add_paper_bibtex.py" \
  --vault "$RESEARCH_ROOT/Postgraduate_Example_Domain"
```

Useful options:

```bash
--master wiki/papers/idea-XX-paper-master.csv
--sleep 0.2
--no-network
```

After meaningful updates, run relation and semantic generation for the root:

```bash
python "$YOUR_AI_POSTGRADUATE_HOME/scripts/generate_vault_relations.py" --root "$RESEARCH_ROOT" --date YYYY-MM-DD
python "$YOUR_AI_POSTGRADUATE_HOME/scripts/generate_semantic_relations.py" --root "$RESEARCH_ROOT" --date YYYY-MM-DD
```
