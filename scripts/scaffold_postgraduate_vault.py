#!/usr/bin/env python3
"""Create Postgraduate Obsidian vault skeletons."""

from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path


INVALID = '<>:"/\\|?*'

DOMAIN_TRANSLATIONS = {
    "教育": "Education",
    "军事": "Military",
    "信息舆论": "Information_Opinion",
    "心理健康": "Mental_Health",
}


def clean_segment(value: str) -> str:
    value = value.strip()
    value = DOMAIN_TRANSLATIONS.get(value, value)
    for source, target in sorted(DOMAIN_TRANSLATIONS.items(), key=lambda item: len(item[0]), reverse=True):
        value = value.replace(source, target)
    value = "".join("_" if char in INVALID else char for char in value)
    value = re.sub(r"[^A-Za-z0-9_ -]+", "_", value)
    value = re.sub(r"[\s-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "Unknown"


def write_if_missing(path: Path, content: str) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def seed_meta(vault: Path, title: str, domain: str, kind: str) -> None:
    today = date.today().isoformat()
    wiki = vault / "wiki"
    write_if_missing(
        wiki / "index.md",
        f"""---
type: meta
domain: "{domain}"
status: active
created: {today}
updated: {today}
tags: [postgraduate, index]
---

# {title} Index

## Core Pages
- [[Overview]]
- [[Hot Cache]]
- [[Log]]

## Catalog

Add generated pages here grouped by type.
""",
    )
    write_if_missing(
        wiki / "log.md",
        f"""---
type: meta
domain: "{domain}"
status: active
created: {today}
updated: {today}
tags: [postgraduate, log]
---

# Log

## {today} | scaffold | {title}
- Vault type: {kind}
- Key change: Initialized postgraduate Obsidian vault skeleton.
""",
    )
    write_if_missing(
        wiki / "hot.md",
        f"""---
type: meta
domain: "{domain}"
status: active
created: {today}
updated: {today}
tags: [postgraduate, hot-cache]
---

# Hot Cache

## Current Focus
This vault has just been initialized.

## Recent Changes
- Created the base postgraduate research vault structure.

## Next Useful Actions
- Ingest seed papers, datasets, or project notes.
""",
    )
    write_if_missing(
        wiki / "overview.md",
        f"""---
type: meta
domain: "{domain}"
status: active
created: {today}
updated: {today}
tags: [postgraduate, overview]
---

# {title} Overview

Purpose: {domain}

This vault is maintained as part of the user's postgraduate research system.
""",
    )


def seed_obsidian_config(vault: Path) -> None:
    obsidian = vault / ".obsidian"
    obsidian.mkdir(parents=True, exist_ok=True)
    write_if_missing(
        obsidian / "app.json",
        """{
  "newFileLocation": "folder",
  "newFileFolderPath": "wiki",
  "attachmentFolderPath": "wiki/sources",
  "alwaysUpdateLinks": true,
  "showUnsupportedFiles": true
}
""",
    )
    write_if_missing(
        obsidian / "core-plugins.json",
        """[
  "file-explorer",
  "global-search",
  "switcher",
  "graph",
  "backlink",
  "outgoing-link",
  "tag-pane",
  "page-preview",
  "templates",
  "note-composer",
  "command-palette"
]
""",
    )
    write_if_missing(
        obsidian / "workspace.json",
        """{
  "main": {
    "id": "postgraduate-main",
    "type": "split",
    "children": []
  },
  "left": {
    "id": "postgraduate-left",
    "type": "split",
    "children": []
  },
  "right": {
    "id": "postgraduate-right",
    "type": "split",
    "children": []
  },
  "active": null
}
""",
    )


def create_domain(root: Path, domain: str) -> Path:
    domain_clean = clean_segment(domain)
    vault_name = f"Postgraduate_{domain_clean}"
    vault = root / vault_name
    dirs = [
        ".raw",
        "rag",
        "wiki/sources",
        "wiki/causal-core/causal-discovery",
        "wiki/causal-core/causal-inference",
        "wiki/causal-core/causal-reasoning",
        "wiki/causal-core/assumptions",
        "wiki/causal-core/methods",
        "wiki/causal-core/benchmarks",
        "wiki/causal-core/datasets",
        "wiki/causal-core/papers",
        "wiki/domain-concepts",
        "wiki/domain-entities",
        "wiki/variables",
        "wiki/mechanisms",
        "wiki/interventions",
        "wiki/datasets",
        "wiki/papers",
        "wiki/surveys",
        "wiki/ideas",
        "wiki/relations",
        "wiki/relations/semantic",
        "wiki/experiments",
        "wiki/causal-bridges",
        "wiki/questions",
        "wiki/claims",
        "wiki/gaps",
        "wiki/meta",
    ]
    for rel in dirs:
        (vault / rel).mkdir(parents=True, exist_ok=True)
    seed_obsidian_config(vault)
    seed_meta(vault, vault_name, domain_clean, "domain")
    return vault


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        default="~/auto-research",
        help="Directory that contains all Postgraduate vaults; defaults to ~/auto-research",
    )
    parser.add_argument("--domain", action="append", default=[], help="Domain name; may be repeated")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    if not args.domain:
        parser.error("at least one --domain is required")
    for domain in args.domain:
        print(f"domain={create_domain(root, domain)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
