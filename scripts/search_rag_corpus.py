#!/usr/bin/env python3
"""Provider-free lexical retrieval over the generated RAG JSONL corpus."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path


TOKEN_RE = re.compile(r"[A-Za-z0-9_+-]+|[\u4e00-\u9fff]")


def tokens(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def matches_filters(item: dict[str, object], args: argparse.Namespace) -> bool:
    metadata = item.get("metadata", {})
    if args.vault and metadata.get("vault") != args.vault:
        return False
    if args.source_type and metadata.get("source_type") not in set(args.source_type):
        return False
    if args.evidence_level and metadata.get("rag_evidence_level") not in set(args.evidence_level):
        return False
    if args.review_status and metadata.get("review_status") not in set(args.review_status):
        return False
    if not args.include_blocked and metadata.get("rag_evidence_level") == "blocked":
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--corpus", default=str(Path.home() / "auto-research/rag/corpus.jsonl"))
    parser.add_argument("--vault")
    parser.add_argument("--source-type", action="append")
    parser.add_argument("--evidence-level", action="append")
    parser.add_argument("--review-status", action="append")
    parser.add_argument("--include-blocked", action="store_true")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    query_tokens = tokens(args.query)
    if not query_tokens:
        raise SystemExit("Query has no searchable tokens")
    query_counts = Counter(query_tokens)
    documents: list[tuple[dict[str, object], Counter[str], int]] = []
    document_frequency: Counter[str] = Counter()
    corpus_path = Path(args.corpus)
    with corpus_path.open(encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            if not matches_filters(item, args):
                continue
            doc_tokens = tokens(str(item.get("text", "")))
            counts = Counter(doc_tokens)
            documents.append((item, counts, len(doc_tokens)))
            for token in query_counts:
                if token in counts:
                    document_frequency[token] += 1

    if not documents:
        raise SystemExit("No records match the selected filters")
    average_length = sum(length for _, _, length in documents) / len(documents)
    k1 = 1.5
    b = 0.75
    scored = []
    total = len(documents)
    for item, counts, length in documents:
        score = 0.0
        for token, query_weight in query_counts.items():
            tf = counts[token]
            if not tf:
                continue
            df = document_frequency[token]
            idf = math.log(1 + (total - df + 0.5) / (df + 0.5))
            denominator = tf + k1 * (1 - b + b * length / max(average_length, 1))
            score += query_weight * idf * (tf * (k1 + 1) / denominator)
        if score > 0:
            scored.append((score, item))
    scored.sort(key=lambda pair: (-pair[0], str(pair[1]["id"])))
    results = [
        {
            "score": round(score, 6),
            "id": item["id"],
            "text": item["text"],
            "metadata": item["metadata"],
        }
        for score, item in scored[: args.top_k]
    ]

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        for index, result in enumerate(results, start=1):
            metadata = result["metadata"]
            print(
                f"[{index}] score={result['score']} id={result['id']} "
                f"source={metadata.get('source_type')} paper={metadata.get('paper_id')} "
                f"page={metadata.get('page')} section={metadata.get('section')}"
            )
            print(str(result["text"])[:800].strip())
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
