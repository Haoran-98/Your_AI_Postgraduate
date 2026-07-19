#!/usr/bin/env python3
"""Retrieve compact paper memories, source chunks, and citation metadata."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

from hyperextract_clients import create_llm_client
from search_rag_corpus import tokens


def load_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def rank_memories(records: list[dict[str, object]], query: str, top_k: int) -> list[dict[str, object]]:
    candidates = [item for item in records if item.get("metadata", {}).get("source_type") == "paper-memory"]
    query_counts = Counter(tokens(query))
    if not query_counts:
        return []
    documents = []
    frequency: Counter[str] = Counter()
    for item in candidates:
        counts = Counter(tokens(str(item.get("text", ""))))
        documents.append((item, counts, sum(counts.values())))
        for token in query_counts:
            if token in counts:
                frequency[token] += 1
    average = sum(length for _, _, length in documents) / max(len(documents), 1)
    scored = []
    for item, counts, length in documents:
        score = 0.0
        for token, query_weight in query_counts.items():
            term_frequency = counts[token]
            if not term_frequency:
                continue
            document_frequency = frequency[token]
            inverse = math.log(1 + (len(documents) - document_frequency + 0.5) / (document_frequency + 0.5))
            denominator = term_frequency + 1.5 * (0.25 + 0.75 * length / max(average, 1))
            score += query_weight * inverse * (term_frequency * 2.5 / denominator)
        if score:
            scored.append((score, item))
    scored.sort(key=lambda value: (-value[0], str(value[1]["id"])))
    return [{"score": round(score, 6), **item} for score, item in scored[:top_k]]


def retrieve(vault: Path, query: str, top_k: int) -> list[dict[str, object]]:
    memory_records = load_jsonl(vault / "rag/paper-memory/corpus.jsonl")
    raw_records = {
        str(item["id"]): item
        for item in load_jsonl(vault / "rag/corpus.jsonl")
    }
    bibliography = {
        str(item["id"]): item
        for item in memory_records
        if item.get("metadata", {}).get("source_type") == "paper-bibliography"
    }
    results = []
    for item in rank_memories(memory_records, query, top_k):
        metadata = item["metadata"]
        results.append(
            {
                "score": item["score"],
                "memory_id": metadata.get("memory_id"),
                "paper_id": metadata.get("paper_id"),
                "kind": metadata.get("memory_kind"),
                "text": item["text"],
                "location": metadata.get("location"),
                "source_chunks": [
                    raw_records[chunk_id]
                    for chunk_id in metadata.get("source_chunk_ids", [])
                    if chunk_id in raw_records
                ],
                "bibliography": bibliography.get(str(metadata.get("bibliography_ref"))),
            }
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("vault")
    parser.add_argument("query")
    parser.add_argument("--root", default=str(Path.home() / "auto-research"))
    parser.add_argument("--top-k", type=int, default=6)
    parser.add_argument("--chat", action="store_true")
    args = parser.parse_args()
    vault = Path(args.vault)
    if not vault.is_absolute():
        vault = Path(args.root).resolve() / vault
    results = retrieve(vault, args.query, args.top_k)
    if not args.chat:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0
    if not results:
        raise SystemExit("No paper memories matched the query")
    llm = create_llm_client(strength="strong", timeout=300)
    response = llm.invoke(
        [
            {
                "role": "system",
                "content": (
                    "Answer the research question using only the retrieved paper memories and source chunks. "
                    "Connect mechanisms and causal evidence conservatively. Cite memory IDs and paper IDs, "
                    "and provide citation keys or BibTeX metadata for claims used."
                ),
            },
            {
                "role": "user",
                "content": f"Question: {args.query}\n\nRetrieved evidence:\n{json.dumps(results, ensure_ascii=False)}",
            },
        ]
    )
    print(response.content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
