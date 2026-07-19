#!/usr/bin/env python3
"""Create a conservative graph containing only source-validated evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from validate_hyperextract_evidence import load_corpus, quote_matches


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("vault", type=Path)
    args = parser.parse_args()

    vault = args.vault.resolve()
    corpus = load_corpus(vault / "rag/corpus.jsonl")
    raw_path = vault / "rag/hyperextract/knowledge-abstract/data.json"
    graph = json.loads(raw_path.read_text(encoding="utf-8"))

    nodes = []
    rejected_nodes = []
    for node in graph.get("nodes", []):
        quotes = [str(value) for value in node.get("evidence_quotes") or []]
        locations = [str(value) for value in node.get("locations") or []]
        kept_quotes = [quote for quote in quotes if quote_matches(quote, locations, corpus)]
        if not kept_quotes:
            rejected_nodes.append(node.get("name"))
            continue
        cleaned = dict(node)
        cleaned["evidence_quotes"] = kept_quotes
        cleaned["review_status"] = "machine-validated"
        nodes.append(cleaned)

    node_names = {node.get("name") for node in nodes}
    edges = []
    rejected_edges = []
    for edge in graph.get("edges", []):
        location = str(edge.get("location") or "")
        quote = str(edge.get("evidence_quote") or "")
        valid = (
            edge.get("source") in node_names
            and edge.get("target") in node_names
            and quote_matches(quote, [location], corpus)
        )
        if not valid:
            rejected_edges.append(
                {
                    "source": edge.get("source"),
                    "type": edge.get("type"),
                    "target": edge.get("target"),
                }
            )
            continue
        cleaned = dict(edge)
        cleaned["review_status"] = "machine-validated"
        edges.append(cleaned)

    output_dir = vault / "rag/hyperextract/validated"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = {
        "nodes": nodes,
        "edges": edges,
        "validation": {
            "source_graph": str(raw_path.relative_to(vault)),
            "raw_nodes": len(graph.get("nodes", [])),
            "raw_edges": len(graph.get("edges", [])),
            "validated_nodes": len(nodes),
            "validated_edges": len(edges),
            "rejected_nodes": rejected_nodes,
            "rejected_edges": rejected_edges,
            "promotion_policy": "machine-validated is not human-verified",
        },
    }
    (output_dir / "data.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(output["validation"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
