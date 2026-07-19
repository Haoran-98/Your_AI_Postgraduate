#!/usr/bin/env python3
"""Build provenance-rich JSONL corpora for RAG and Hyper-Extract ingestion."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Iterable


SCHEMA_VERSION = "1.0"
RAG_MARKER_START = "<!-- RAG-LAYER-START -->"
RAG_MARKER_END = "<!-- RAG-LAYER-END -->"
CURATED_FOLDERS = {
    "causal-bridges",
    "claims",
    "datasets",
    "gaps",
    "hypotheses",
    "ideas",
    "mechanisms",
    "sources",
    "surveys",
    "variables",
}
HEADING_RE = re.compile(
    r"^(?:\d+(?:\.\d+)*\s+)?(?:abstract|introduction|background|related work|method(?:s|ology)?|"
    r"materials and methods|experimental setup|experiment(?:s)?|evaluation|results?|discussion|"
    r"limitations?|threats to validity|conclusion(?:s)?|references|appendix)(?:\s|$)",
    re.I,
)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    raw = text[4:end]
    body = text[end + 5 :]
    values: dict[str, str] = {}
    for line in raw.splitlines():
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if match and match.group(2) not in {"|", ">"}:
            values[match.group(1)] = match.group(2).strip().strip('"')
    return values, body


def markdown_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def paper_card(vault: Path, paper_id: str) -> Path | None:
    matches = sorted((vault / "wiki/papers").glob(f"{paper_id}-*.md"))
    return matches[0] if matches else None


def status_rows(vault: Path) -> list[dict[str, str]]:
    path = vault / ".raw/fulltext-status.csv"
    if path.exists():
        with path.open(newline="", encoding="utf-8", errors="ignore") as handle:
            return list(csv.DictReader(handle))

    rows = []
    for card in sorted((vault / "wiki/papers").glob("P*.md")):
        paper_id = card.name.split("-", 1)[0]
        card_text = card.read_text(encoding="utf-8", errors="ignore")
        fm, _ = parse_frontmatter(card_text)
        text_candidates = sorted((vault / ".raw/fulltext-text").glob(f"{paper_id}-*.txt"))
        pdf_candidates = sorted((vault / ".raw/fulltext-pdfs").glob(f"{paper_id}-*.pdf"))
        local_text = fm.get("local_text", "")
        local_pdf = fm.get("local_pdf", "")
        if not local_text and text_candidates:
            local_text = str(text_candidates[0].relative_to(vault))
        if not local_pdf and pdf_candidates:
            local_pdf = str(pdf_candidates[0].relative_to(vault))
        status = fm.get("status", "fulltext-blocked")
        if status == "fulltext-read" and not local_text:
            status = "fulltext-blocked"
        rows.append(
            {
                "id": paper_id,
                "title": markdown_title(card_text, paper_id),
                "url": "",
                "status": status,
                "pdf": local_pdf,
                "text": local_text,
                "reason": fm.get("blocked_reason", "paper-card-derived-status"),
                "lines": "",
                "words": "",
            }
        )
    return rows


def detect_heading(line: str) -> str | None:
    value = re.sub(r"\s+", " ", line).strip().strip("#")
    if not value or len(value) > 120:
        return None
    if HEADING_RE.match(value):
        return value
    if re.match(r"^\d+(?:\.\d+)*\s+[A-Z][A-Za-z0-9 ,:/()-]{2,80}$", value):
        return value
    return None


def paragraphs_with_location(text: str, include_references: bool) -> list[tuple[int | None, str, str]]:
    pages = text.split("\f") if "\f" in text else [text]
    located: list[tuple[int | None, str, str]] = []
    section = "unknown"
    references_seen = False
    for page_index, page in enumerate(pages, start=1):
        page_number = page_index if len(pages) > 1 else None
        buffer: list[str] = []

        def flush() -> None:
            if not buffer:
                return
            paragraph = re.sub(r"\s+", " ", " ".join(buffer)).strip()
            buffer.clear()
            if paragraph and (include_references or not references_seen):
                located.append((page_number, section, paragraph))

        for raw_line in page.splitlines():
            line = raw_line.strip()
            if not line:
                flush()
                continue
            heading = detect_heading(line)
            if heading:
                flush()
                section = heading
                if re.match(r"^(?:\d+(?:\.\d+)*\s+)?references(?:\s|$)", heading, re.I):
                    references_seen = True
                continue
            buffer.append(line)
        flush()
    return located


def split_long_text(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        if end < len(text):
            boundary = text.rfind(" ", start + max_chars // 2, end)
            if boundary > start:
                end = boundary
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(start + 1, end - overlap_chars)
    return [chunk for chunk in chunks if chunk]


def pack_located_paragraphs(
    items: list[tuple[int | None, str, str]], max_chars: int, overlap_chars: int
) -> list[tuple[int | None, str, str]]:
    output: list[tuple[int | None, str, str]] = []
    current_page: int | None = None
    current_section = "unknown"
    current: list[str] = []

    def flush() -> None:
        if not current:
            return
        joined = "\n\n".join(current).strip()
        current.clear()
        for part in split_long_text(joined, max_chars, overlap_chars):
            output.append((current_page, current_section, part))

    for page, section, paragraph in items:
        if current and (page != current_page or section != current_section):
            flush()
        if not current:
            current_page, current_section = page, section
        prospective = "\n\n".join([*current, paragraph])
        if current and len(prospective) > max_chars:
            previous_tail = " ".join(current)[-overlap_chars:].strip()
            flush()
            current_page, current_section = page, section
            if previous_tail:
                current.append(previous_tail)
        current.append(paragraph)
    flush()
    return output


def markdown_chunks(text: str, max_chars: int, overlap_chars: int) -> list[tuple[str, str]]:
    _, body = parse_frontmatter(text)
    section = "document"
    pieces: list[tuple[int | None, str, str]] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            value = re.sub(r"\n{3,}", "\n\n", "\n".join(buffer)).strip()
            buffer.clear()
            if value:
                pieces.append((None, section, value))

    for line in body.splitlines():
        if line.startswith("#"):
            flush()
            section = line.lstrip("#").strip() or section
        else:
            buffer.append(line)
    flush()
    return [(sec, value) for _, sec, value in pack_located_paragraphs(pieces, max_chars, overlap_chars)]


def record(
    *,
    chunk_id: str,
    text: str,
    metadata: dict[str, object],
) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "id": chunk_id,
        "text": text,
        "text_sha256": sha256_text(text),
        "metadata": metadata,
    }


def fulltext_records(
    vault: Path,
    row: dict[str, str],
    max_chars: int,
    overlap_chars: int,
    include_references: bool,
) -> Iterable[dict[str, object]]:
    if row.get("status") != "fulltext-read" or not row.get("text"):
        return
    local_text = vault / row["text"]
    if not local_text.exists():
        return
    card = paper_card(vault, row["id"])
    card_text = card.read_text(encoding="utf-8", errors="ignore") if card else ""
    fm, _ = parse_frontmatter(card_text)
    title = row.get("title") or markdown_title(card_text, row["id"])
    source_text = local_text.read_text(encoding="utf-8", errors="ignore")
    located = paragraphs_with_location(source_text, include_references)
    chunks = pack_located_paragraphs(located, max_chars, overlap_chars)
    for index, (page, section, chunk) in enumerate(chunks, start=1):
        chunk_id = f"{vault.name}:{row['id']}:fulltext:{index:05d}"
        yield record(
            chunk_id=chunk_id,
            text=chunk,
            metadata={
                "vault": vault.name,
                "idea_id": fm.get("idea_id", "unknown"),
                "paper_id": row["id"],
                "title": title,
                "source_type": "paper-fulltext",
                "source_path": row["text"],
                "local_pdf": row.get("pdf", ""),
                "page": page,
                "section": section,
                "chunk_index": index,
                "original_status": fm.get("status", row.get("status", "")),
                "original_evidence_level": fm.get("evidence_level", ""),
                "rag_evidence_level": "fulltext-available-machine-screened",
                "review_status": "unreviewed",
            },
        )


def paper_card_record(vault: Path, row: dict[str, str], max_chars: int, overlap_chars: int) -> Iterable[dict[str, object]]:
    card = paper_card(vault, row["id"])
    if not card:
        return
    card_text = card.read_text(encoding="utf-8", errors="ignore")
    fm, _ = parse_frontmatter(card_text)
    title = markdown_title(card_text, row.get("title", row["id"]))
    for index, (section, chunk) in enumerate(markdown_chunks(card_text, max_chars, overlap_chars), start=1):
        yield record(
            chunk_id=f"{vault.name}:{row['id']}:paper-card:{index:04d}",
            text=chunk,
            metadata={
                "vault": vault.name,
                "idea_id": fm.get("idea_id", "unknown"),
                "paper_id": row["id"],
                "title": title,
                "source_type": "paper-card",
                "source_path": str(card.relative_to(vault)),
                "section": section,
                "original_status": fm.get("status", row.get("status", "")),
                "original_evidence_level": fm.get("evidence_level", ""),
                "rag_evidence_level": "blocked" if row.get("status") != "fulltext-read" else "machine-synthesis",
                "review_status": "unreviewed",
            },
        )


def curated_records(vault: Path, max_chars: int, overlap_chars: int) -> Iterable[dict[str, object]]:
    wiki = vault / "wiki"
    paths: list[Path] = []
    for folder in CURATED_FOLDERS:
        root = wiki / folder
        if root.exists():
            paths.extend(root.rglob("*.md"))
    assumptions = wiki / "causal-core/assumptions"
    if assumptions.exists():
        paths.extend(assumptions.rglob("*.md"))
    for path in sorted(set(paths)):
        text = path.read_text(encoding="utf-8", errors="ignore")
        fm, _ = parse_frontmatter(text)
        title = markdown_title(text, path.stem)
        source_type = fm.get("type", path.parent.name)
        for index, (section, chunk) in enumerate(markdown_chunks(text, max_chars, overlap_chars), start=1):
            yield record(
                chunk_id=f"{vault.name}:wiki:{path.stem}:{index:04d}",
                text=chunk,
                metadata={
                    "vault": vault.name,
                    "idea_id": fm.get("idea_id", "unknown"),
                    "paper_id": "",
                    "title": title,
                    "source_type": f"wiki-{source_type}",
                    "source_path": str(path.relative_to(vault)),
                    "section": section,
                    "original_status": fm.get("status", ""),
                    "original_evidence_level": fm.get("evidence_level", ""),
                    "rag_evidence_level": fm.get("evidence_level", "derived-synthesis"),
                    "review_status": fm.get("review_status", "unreviewed"),
                },
            )


def write_readme(vault: Path, manifest: dict[str, object]) -> None:
    rag = vault / "rag"
    content = f"""# RAG Corpus

Generated: {manifest['generated']}
Schema: `{SCHEMA_VERSION}`
Records: {manifest['records']}

`corpus.jsonl` is the canonical retrieval corpus. Each line contains `id`, `text`, `text_sha256`, and provenance-rich `metadata`.

Recommended retrieval filters:

- Strongest source layer: `source_type == paper-fulltext`.
- Exclude bibliography-only records: `rag_evidence_level != blocked`.
- Treat `machine-synthesis` and `derived-synthesis` as navigation or hypothesis material until reviewed.
- Do not promote Hyper-Extract output to verified evidence unless `review_status` becomes `human-verified`.

Hyper-Extract writes its graph Knowledge Abstract to `hyperextract/knowledge-abstract/` and its browsable Obsidian graph to `hyperextract/obsidian/` when the extraction runner is executed with a configured model and embedder.
"""
    (rag / "README.md").write_text(content, encoding="utf-8")


def upsert_marker(text: str, content: str) -> str:
    block = f"{RAG_MARKER_START}\n{content.strip()}\n{RAG_MARKER_END}"
    pattern = re.compile(
        re.escape(RAG_MARKER_START) + r".*?" + re.escape(RAG_MARKER_END), re.S
    )
    if pattern.search(text):
        return pattern.sub(block, text)
    return text.rstrip() + "\n\n" + block + "\n"


def write_vault_rag_note(vault: Path, manifest: dict[str, object]) -> None:
    idea_id = str(manifest.get("idea_id", "idea-xx"))
    relations = vault / "wiki/relations"
    relations.mkdir(parents=True, exist_ok=True)
    note = relations / f"{idea_id}-rag-layer.md"
    counts = manifest["source_type_counts"]
    fulltext = counts.get("paper-fulltext", 0)
    cards = counts.get("paper-card", 0)
    content = f"""---
type: rag-layer
domain: {vault.name.replace('Postgraduate_', '')}
status: active
updated: {manifest['generated']}
idea_id: {idea_id}
evidence_level: mixed-filter-required
---

# {idea_id} RAG And Hyper-Extract Layer

## Current State

- RAG records: {manifest['records']}.
- Paper full-text chunks: {fulltext}.
- Paper-card chunks: {cards}.
- Hyper-Extract status: `{manifest['hyperextract_status']}`.
- Corpus: [rag/corpus.jsonl](../../rag/corpus.jsonl).
- Manifest: [rag/manifest.json](../../rag/manifest.json).
- Usage and evidence filters: [[rag/README]].

## Retrieval Policy

- Prefer `source_type=paper-fulltext` for evidence retrieval.
- Exclude `rag_evidence_level=blocked`.
- Treat `machine-synthesis` and `derived-synthesis` as navigation until reviewed.
- Hyper-Extract graph nodes and edges remain `machine-extracted` until their evidence spans are checked against the local source.

## Derived Outputs

- Hyper graph data: `rag/hyperextract/knowledge-abstract/data.json` after model execution.
- FAISS index: `rag/hyperextract/knowledge-abstract/index/` after model execution.
- Browsable Obsidian graph: `rag/hyperextract/obsidian/` after model execution.
"""
    note.write_text(content, encoding="utf-8")
    index = vault / "wiki/index.md"
    if index.exists():
        index_text = index.read_text(encoding="utf-8", errors="ignore")
        index_section = f"""## RAG And Hyper-Extract
- RAG status and evidence filters: [[{note.stem}]].
- Provider-neutral corpus: [rag/corpus.jsonl](../rag/corpus.jsonl).
"""
        index.write_text(upsert_marker(index_text, index_section), encoding="utf-8")


def write_root_readme(root_rag: Path, manifest: dict[str, object]) -> None:
    content = f"""# Global RAG Corpus

Generated: {manifest['generated']}
Schema: `{SCHEMA_VERSION}`
Records: {manifest['records']}
Vaults: {len(manifest['vaults'])}

`corpus.jsonl` combines the per-vault corpora for cross-domain retrieval. Use metadata filters for `vault`, `source_type`, `rag_evidence_level`, and `review_status` before generation.

Current Hyper-Extract status: `{manifest['hyperextract_status']}`. The corpus is immediately usable by external RAG systems and the provider-free lexical smoke test. Graph extraction and FAISS indexing require a configured Hyper-Extract LLM and embedder.

```bash
python scripts/search_rag_corpus.py \
  "causal discovery domain constraints" \
  --vault Postgraduate_Example_Domain \
  --source-type paper-fulltext
```
"""
    (root_rag / "README.md").write_text(content, encoding="utf-8")


def selected_vaults(root: Path, requested: list[str]) -> list[Path]:
    if not requested:
        return sorted(path for path in root.glob("Postgraduate_*") if path.is_dir())
    result = []
    for value in requested:
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = root / value
        if not candidate.is_dir():
            raise SystemExit(f"Vault not found: {candidate}")
        result.append(candidate)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path.home() / "auto-research"))
    parser.add_argument("--vault", action="append", default=[])
    parser.add_argument("--chunk-size", type=int, default=1600)
    parser.add_argument("--overlap", type=int, default=200)
    parser.add_argument("--include-references", action="store_true")
    parser.add_argument("--fulltext-only", action="store_true")
    parser.add_argument("--limit-papers", type=int)
    parser.add_argument("--skip-global", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    root_rag = root / "rag"
    root_rag.mkdir(parents=True, exist_ok=True)
    global_path = root_rag / (".corpus.skip-global.tmp" if args.skip_global else "corpus.jsonl")
    global_counts: Counter[str] = Counter()
    vault_manifests = []

    with global_path.open("w", encoding="utf-8") as global_out:
        for vault in selected_vaults(root, args.vault):
            rows = status_rows(vault)
            if args.limit_papers:
                rows = rows[: args.limit_papers]
            rag = vault / "rag"
            rag.mkdir(parents=True, exist_ok=True)
            corpus_path = rag / "corpus.jsonl"
            counts: Counter[str] = Counter()
            record_count = 0
            seen_ids: set[str] = set()
            with corpus_path.open("w", encoding="utf-8") as output:
                sources: list[Iterable[dict[str, object]]] = []
                for row in rows:
                    sources.append(fulltext_records(vault, row, args.chunk_size, args.overlap, args.include_references))
                    if not args.fulltext_only:
                        sources.append(paper_card_record(vault, row, args.chunk_size, args.overlap))
                if not args.fulltext_only:
                    sources.append(curated_records(vault, args.chunk_size, args.overlap))
                for source in sources:
                    if source is None:
                        continue
                    for item in source:
                        if item["id"] in seen_ids:
                            continue
                        seen_ids.add(item["id"])
                        line = json.dumps(item, ensure_ascii=False)
                        output.write(line + "\n")
                        global_out.write(line + "\n")
                        source_type = str(item["metadata"]["source_type"])
                        counts[source_type] += 1
                        global_counts[source_type] += 1
                        record_count += 1
            manifest = {
                "schema_version": SCHEMA_VERSION,
                "generated": date.today().isoformat(),
                "vault": vault.name,
                "idea_id": next(
                    (
                        parse_frontmatter(card.read_text(encoding="utf-8", errors="ignore"))[0].get("idea_id", "idea-xx")
                        for row in rows
                        if (card := paper_card(vault, row["id"])) is not None
                    ),
                    "idea-xx",
                ),
                "records": record_count,
                "chunk_size": args.chunk_size,
                "overlap": args.overlap,
                "include_references": args.include_references,
                "source_type_counts": dict(sorted(counts.items())),
                "corpus": "rag/corpus.jsonl",
                "hyperextract_template": "integrations/hyperextract/academic_causal_evidence_graph.yaml",
                "hyperextract_status": "pending-model-execution",
            }
            (rag / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            write_readme(vault, manifest)
            write_vault_rag_note(vault, manifest)
            vault_manifests.append(manifest)
            print(f"{vault.name}\trecords={record_count}\tcorpus={corpus_path}")

    if args.skip_global:
        global_path.unlink(missing_ok=True)
        return 0

    global_manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated": date.today().isoformat(),
        "records": sum(item["records"] for item in vault_manifests),
        "vaults": [item["vault"] for item in vault_manifests],
        "source_type_counts": dict(sorted(global_counts.items())),
        "corpus": "rag/corpus.jsonl",
        "hyperextract_status": "pending-model-execution",
    }
    (root_rag / "manifest.json").write_text(json.dumps(global_manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_root_readme(root_rag, global_manifest)
    print(f"GLOBAL\trecords={global_manifest['records']}\tcorpus={global_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
