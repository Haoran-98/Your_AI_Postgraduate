---
name: postgraduate-fulltext-acquirer
description: "Acquire lawful scholarly full text and OCR scanned PDFs for Postgraduate vaults. Use when the user asks to download papers, resolve arXiv/ACL/DOI PDF links, extract text, mark blocked papers, or recover image-only documents."
---

# Postgraduate Fulltext Acquirer

Read `../postgraduate-common/references/evidence-policy.md` and `privacy-publication.md`.

## Workflow

1. Read the paper master and existing paper-card URL/DOI metadata.
2. Prefer direct official PDF, arXiv, ACL Anthology, then DOI/publisher discovery.
3. Preserve PDFs under `.raw/fulltext-pdfs/` and text under `.raw/fulltext-text/`.
4. Use OCR only when ordinary extraction is empty or image-only.
5. Mark readable papers `fulltext-read`; mark unavailable papers `fulltext-blocked` with a concrete reason.
6. Never fabricate full text or bypass access controls.

```bash
python scripts/acquire_fulltexts.py --root "$RESEARCH_ROOT" --vault Postgraduate_Example_Domain
python scripts/ocr_scanned_pdf.py input.pdf output.txt
```
