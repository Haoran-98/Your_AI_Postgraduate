#!/usr/bin/env python3
"""Search or chat with a vault's Hyper-Extract graph index."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from hyperextract_clients import create_hyperextract_clients


def serialize(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, tuple):
        return [serialize(item) for item in value]
    if isinstance(value, list):
        return [serialize(item) for item in value]
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("vault", help="Vault name or absolute path")
    parser.add_argument("query")
    parser.add_argument("--root", default=str(Path.home() / "auto-research"))
    parser.add_argument(
        "--template",
        default="integrations/hyperextract/academic_causal_evidence_graph.yaml",
    )
    parser.add_argument("--language", default="en", choices=["en", "zh"])
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--chat", action="store_true")
    parser.add_argument("--raw", action="store_true", help="Query the unvalidated machine graph")
    args = parser.parse_args()

    try:
        from hyperextract import Template
    except ImportError as exc:
        raise SystemExit("Hyper-Extract is not installed in this Python environment") from exc

    root = Path(args.root).resolve()
    vault = Path(args.vault)
    if not vault.is_absolute():
        vault = root / vault
    template = Path(args.template)
    if not template.is_absolute():
        template = root / template
    validated_path = vault / "rag/hyperextract/validated"
    ka_path = vault / "rag/hyperextract/knowledge-abstract" if args.raw else validated_path
    if not (ka_path / "data.json").exists():
        raise SystemExit(f"Knowledge Abstract not found: {ka_path}")

    llm_client, embedder = create_hyperextract_clients(strength="strong")
    ka = Template.create(
        str(template),
        args.language,
        llm_client=llm_client,
        embedder=embedder,
    )
    ka.load(ka_path)
    if args.chat:
        response = ka.chat(args.query, top_k=args.top_k)
        print(response.content)
        retrieved = {
            "nodes": serialize(response.additional_kwargs.get("retrieved_nodes", [])),
            "edges": serialize(response.additional_kwargs.get("retrieved_edges", [])),
        }
        print(json.dumps(retrieved, indent=2, ensure_ascii=False))
    else:
        nodes, edges = ka.search(args.query, top_k=args.top_k)
        print(json.dumps({"nodes": serialize(nodes), "edges": serialize(edges)}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
