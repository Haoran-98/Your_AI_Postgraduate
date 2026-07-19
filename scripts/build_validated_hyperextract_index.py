#!/usr/bin/env python3
"""Build search and Obsidian artifacts from the machine-validated graph."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from hyperextract_clients import create_hyperextract_clients


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("vault", type=Path)
    parser.add_argument("--root", type=Path, default=Path.home() / "auto-research")
    parser.add_argument(
        "--template",
        type=Path,
        default=Path("integrations/hyperextract/academic_causal_evidence_graph.yaml"),
    )
    parser.add_argument("--language", default="en", choices=["en", "zh"])
    args = parser.parse_args()

    root = args.root.resolve()
    vault = args.vault if args.vault.is_absolute() else root / args.vault
    template = args.template if args.template.is_absolute() else root / args.template
    raw = vault / "rag/hyperextract/knowledge-abstract"
    validated = vault / "rag/hyperextract/validated"
    obsidian = vault / "rag/hyperextract/obsidian-validated"
    if not (validated / "data.json").exists():
        raise SystemExit(f"Validated graph missing: {validated / 'data.json'}")
    if not (raw / "metadata.json").exists():
        raise SystemExit(f"Raw metadata missing: {raw / 'metadata.json'}")
    shutil.copy2(raw / "metadata.json", validated / "metadata.json")

    from hyperextract import Template

    llm_client, embedder = create_hyperextract_clients()
    ka = Template.create(
        str(template),
        args.language,
        llm_client=llm_client,
        embedder=embedder,
    )
    ka.load(validated)
    ka.build_index()
    ka.dump(validated)
    if obsidian.exists():
        shutil.rmtree(obsidian)
    ka.export_obsidian(
        obsidian,
        vault_name=f"{vault.name} Validated Hyper-Extract Evidence Graph",
        overwrite=True,
    )
    print(f"validated_index={validated}\tobsidian={obsidian}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
