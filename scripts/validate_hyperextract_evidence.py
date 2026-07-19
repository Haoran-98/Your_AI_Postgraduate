#!/usr/bin/env python3
"""Validate Hyper-Extract graph provenance against the source RAG corpus."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


CAUSAL_RELATIONS = {"causes", "mediates", "moderates"}
WEAK_CAUSAL_STRENGTH = {"", "none", "correlational", "associational"}
CHUNK_RE = re.compile(r"(?:^|\|)chunk=([^|]+)")


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def load_corpus(path: Path) -> dict[str, dict[str, object]]:
    records = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            records[str(item["id"])] = item
    return records


def location_chunks(location: str) -> list[str]:
    match = CHUNK_RE.search(location)
    if match:
        return [value.strip() for value in match.group(1).split(",") if value.strip()]
    return [
        value.strip()
        for value in location.split("|")
        if ":fulltext:" in value or ":paper-card:" in value
    ]


def quote_matches(quote: str, locations: list[str], corpus: dict[str, dict[str, object]]) -> bool:
    expected = normalized(quote)
    if not expected:
        return False
    for location in locations:
        for chunk_id in location_chunks(location):
            item = corpus.get(chunk_id)
            if item and expected in normalized(str(item.get("text", ""))):
                return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("vault", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    vault = args.vault.resolve()
    corpus = load_corpus(vault / "rag/corpus.jsonl")
    graph_path = vault / "rag/hyperextract/knowledge-abstract/data.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    node_names = {node.get("name") for node in nodes}
    issues: list[dict[str, object]] = []
    quote_counts = Counter()

    for index, node in enumerate(nodes):
        quotes = node.get("evidence_quotes") or []
        locations = node.get("locations") or []
        for quote in quotes:
            matched = quote_matches(str(quote), [str(value) for value in locations], corpus)
            quote_counts["matched" if matched else "unmatched"] += 1
            if not matched:
                issues.append({"kind": "node_quote_unmatched", "index": index, "name": node.get("name"), "quote": quote})
        if node.get("review_status") != "machine-extracted":
            issues.append({"kind": "invalid_node_review_status", "index": index, "name": node.get("name")})
        confidence = node.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            issues.append({"kind": "invalid_node_confidence", "index": index, "name": node.get("name")})

    for index, edge in enumerate(edges):
        if edge.get("source") not in node_names or edge.get("target") not in node_names:
            issues.append({"kind": "missing_edge_endpoint", "index": index, "source": edge.get("source"), "target": edge.get("target")})
        quote = str(edge.get("evidence_quote") or "")
        location = str(edge.get("location") or "")
        matched = quote_matches(quote, [location], corpus)
        quote_counts["matched" if matched else "unmatched"] += 1
        if not matched:
            issues.append({"kind": "edge_quote_unmatched", "index": index, "source": edge.get("source"), "target": edge.get("target"), "quote": quote})
        if edge.get("review_status") != "machine-extracted":
            issues.append({"kind": "invalid_edge_review_status", "index": index})
        if edge.get("type") in CAUSAL_RELATIONS and edge.get("causal_strength") in WEAK_CAUSAL_STRENGTH:
            issues.append({"kind": "weakly_supported_causal_relation", "index": index, "type": edge.get("type")})

    report = {
        "vault": vault.name,
        "nodes": len(nodes),
        "edges": len(edges),
        "quotes": dict(quote_counts),
        "issues": issues,
        "passed": not issues,
    }
    output = args.output or vault / "rag/hyperextract/validation-report.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
