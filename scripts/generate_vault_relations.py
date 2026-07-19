#!/usr/bin/env python3
"""Generate intra-vault Obsidian relation maps and backlink sections."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path


MARKER_RELATION_LAYER = "RELATION-LAYER"
MARKER_OBSIDIAN_RELATIONS = "OBSIDIAN-RELATIONS"


@dataclass
class VaultStats:
    vault: Path
    idea_id: str
    papers: int
    knowledge_pages: int
    relation_maps: int
    linked_files: int
    total_markdown: int
    total_wikilinks: int


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def write_text(path: Path, text: str, dry_run: bool) -> None:
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def h1(path: Path) -> str:
    for line in read_text(path).splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def first(wiki: Path, subdir: str, pattern: str) -> Path | None:
    folder = wiki / subdir
    if not folder.exists():
        return None
    matches = sorted(folder.glob(pattern))
    return matches[0] if matches else None


def idea_id_from_vault(wiki: Path) -> tuple[str, Path] | None:
    cards = sorted((wiki / "ideas").glob("idea-*-direction-card.md")) if (wiki / "ideas").exists() else []
    if cards:
        match = re.search(r"(idea-\d+)", cards[0].name)
        if match:
            return match.group(1), cards[0]

    for path in sorted(wiki.rglob("idea-*.md")):
        match = re.search(r"(idea-\d+)", path.name)
        if match:
            return match.group(1), path
    return None


def update_frontmatter_date(text: str, today: str) -> str:
    return re.sub(r"updated: \d{4}-\d{2}-\d{2}", f"updated: {today}", text, count=1)


def upsert_marker(text: str, marker: str, section: str) -> str:
    start = f"<!-- {marker}-START -->"
    end = f"<!-- {marker}-END -->"
    replacement = section.strip()
    if start in text and end in text:
        pattern = re.compile(rf"\n?{re.escape(start)}.*?{re.escape(end)}\n?", re.S)
        return pattern.sub("\n" + replacement + "\n", text)
    if text and not text.endswith("\n"):
        text += "\n"
    return text + "\n" + replacement + "\n"


def knowledge_pages(wiki: Path, idea_id: str) -> list[tuple[str, Path]]:
    result: list[tuple[str, Path]] = []
    folders = [
        ("变量", "variables"),
        ("机制", "mechanisms"),
        ("数据/代码", "datasets"),
        ("因果桥", "causal-bridges"),
        ("研究缺口", "gaps"),
        ("证据 claims", "claims"),
        ("干预/应用", "interventions"),
    ]
    for label, subdir in folders:
        folder = wiki / subdir
        if not folder.exists():
            continue
        for path in sorted(folder.glob(f"{idea_id}-*.md")):
            result.append((label, path))
    return result


def build_relation_map(
    vault: Path,
    wiki: Path,
    idea_id: str,
    idea_card: Path,
    core_links: list[tuple[str, Path]],
    knowledge: list[tuple[str, Path]],
    papers: list[Path],
    today: str,
) -> str:
    domain = vault.name.removeprefix("Postgraduate_")
    lines = [
        "---",
        "type: relation-map",
        f"domain: {domain}",
        "status: active",
        f"updated: {today}",
        f"idea_id: {idea_id}",
        "tags: [postgraduate, relation-map, obsidian-graph]",
        "---",
        "",
        f"# {idea_id} 关系图",
        "",
        "本页是该 idea 的 Obsidian 关系枢纽，用来把方向定义、文献证据、知识抽取页和大综述连成可导航图谱。",
        "",
        "## 核心入口",
    ]
    for label, path in core_links:
        lines.append(f"- {label}: [[{path.stem}]]")

    lines.extend(["", "## 知识抽取层"])
    if knowledge:
        for label, path in knowledge:
            lines.append(f"- {label}: [[{path.stem}]]")
    else:
        lines.append("- 暂无知识抽取页；新增变量、机制、数据集、因果桥、gap 或 claim 后重新运行本脚本。")

    target_links = "、".join(f"[[{path.stem}]]" for _, path in knowledge[:6]) if knowledge else "知识抽取页"
    lines.extend(
        [
            "",
            "## 论文证据层",
            "每篇 paper card 作为证据节点，统一回连到变量、机制、数据/代码、因果桥、gap 与 claim 页面。",
        ]
    )
    if papers:
        for path in papers:
            paper_id = path.name.split("-", 1)[0]
            title = h1(path).replace("|", "/")
            lines.append(f"- [[{path.stem}|{paper_id} {title}]] -> {target_links}")
    else:
        lines.append("- 暂无 paper card；新增 `wiki/papers/P*.md` 后重新运行本脚本。")

    survey = first(wiki, "surveys", f"{idea_id}-*.md")
    master = first(wiki, "papers", f"{idea_id}-paper-master.md")
    lines.extend(["", "## 阅读路径", f"1. 从 [[{idea_card.stem}]] 确认 idea 边界。"])
    if master:
        lines.append(f"2. 进入 [[{master.stem}]] 查看文献清单与开源数据/代码字段。")
    if knowledge:
        lines.append("3. 沿知识抽取层检查变量、机制、数据集、因果桥、gap 与 claim 是否互相支撑。")
    if survey:
        lines.append(f"4. 回到 [[{survey.stem}]] 阅读围绕 idea 的大综述，并核对每节末尾的深度分析。")

    lines.extend(
        [
            "",
            "## 关系维护规则",
            "- 新增文献时，同时更新 paper master、paper card 和本页论文证据层。",
            "- 发现代码、数据集或 artifact 链接时，优先更新数据/代码层，再从相关 paper card 建立链接。",
            "- 综述中出现的核心判断必须能回溯到 paper card、claim 或 causal bridge。",
            "",
        ]
    )
    return "\n".join(lines)


def relation_section(core_links: list[tuple[str, Path]], knowledge: list[tuple[str, Path]], for_knowledge_page: bool) -> str:
    lines = [f"<!-- {MARKER_OBSIDIAN_RELATIONS}-START -->", "", "## Obsidian 关系"]
    for label, path in core_links:
        lines.append(f"- {label}: [[{path.stem}]]")
    if for_knowledge_page:
        lines.append("- 本页用于承接 paper cards 中抽取出的可复用知识，并回连到综述论证链。")
    elif knowledge:
        links = "、".join(f"[[{path.stem}|{label}]]" for label, path in knowledge)
        lines.append(f"- 知识抽取: {links}")
    lines.append(f"<!-- {MARKER_OBSIDIAN_RELATIONS}-END -->")
    return "\n".join(lines)


def update_index_hot_log(wiki: Path, relation_map: Path, idea_id: str, today: str, dry_run: bool) -> None:
    index = wiki / "index.md"
    if index.exists():
        section = f"""<!-- {MARKER_RELATION_LAYER}-START -->

## Relation Layer
- Relation map: [[{relation_map.stem}]]
- Use this as the graph hub connecting direction, paper corpus, extracted knowledge, artifacts, claims, and survey.
<!-- {MARKER_RELATION_LAYER}-END -->"""
        text = update_frontmatter_date(upsert_marker(read_text(index), MARKER_RELATION_LAYER, section), today)
        write_text(index, text, dry_run)

    hot = wiki / "hot.md"
    if hot.exists():
        section = f"""<!-- {MARKER_RELATION_LAYER}-START -->

## Relation Layer
- Current graph hub: [[{relation_map.stem}]]
- Use it to navigate from idea to paper evidence, variables, mechanisms, datasets/artifacts, causal bridge, gaps, claims, and long survey.
<!-- {MARKER_RELATION_LAYER}-END -->"""
        text = update_frontmatter_date(upsert_marker(read_text(hot), MARKER_RELATION_LAYER, section), today)
        write_text(hot, text, dry_run)

    log = wiki / "log.md"
    if log.exists():
        line = f"- {today}: Generated or refreshed relation-map hub for {idea_id}."
        text = read_text(log)
        if line not in text:
            if text and not text.endswith("\n"):
                text += "\n"
            text += "\n## Relation Layer Update\n" + line + "\n"
        text = update_frontmatter_date(text, today)
        write_text(log, text, dry_run)


def process_vault(vault: Path, today: str, dry_run: bool) -> VaultStats | None:
    wiki = vault / "wiki"
    if not wiki.exists():
        return None
    detected = idea_id_from_vault(wiki)
    if not detected:
        return None
    idea_id, idea_card = detected

    relation_dir = wiki / "relations"
    relation_map = relation_dir / f"{idea_id}-relation-map.md"
    master = first(wiki, "papers", f"{idea_id}-paper-master.md")
    survey = first(wiki, "surveys", f"{idea_id}-*.md")
    search_notes = first(wiki, "sources", f"{idea_id}-*.md")
    knowledge = knowledge_pages(wiki, idea_id)
    papers = sorted((wiki / "papers").glob("P*.md")) if (wiki / "papers").exists() else []

    core_links = [("关系图", relation_map), ("方向卡", idea_card)]
    if master:
        core_links.append(("论文总表", master))
    if survey:
        core_links.append(("大综述", survey))
    if search_notes:
        core_links.append(("检索记录", search_notes))

    relation_text = build_relation_map(vault, wiki, idea_id, idea_card, core_links[1:], knowledge, papers, today)
    write_text(relation_map, relation_text, dry_run)

    paper_section = relation_section(core_links, knowledge, for_knowledge_page=False)
    for path in papers:
        text = update_frontmatter_date(upsert_marker(read_text(path), MARKER_OBSIDIAN_RELATIONS, paper_section), today)
        write_text(path, text, dry_run)

    knowledge_section = relation_section(core_links, knowledge, for_knowledge_page=True)
    for _, path in knowledge:
        text = update_frontmatter_date(upsert_marker(read_text(path), MARKER_OBSIDIAN_RELATIONS, knowledge_section), today)
        write_text(path, text, dry_run)

    update_index_hot_log(wiki, relation_map, idea_id, today, dry_run)

    markdown_files = list(wiki.rglob("*.md"))
    linked_files = 0
    total_links = 0
    for path in markdown_files:
        text = read_text(path)
        links = re.findall(r"\[\[[^\]]+\]\]", text)
        if links:
            linked_files += 1
            total_links += len(links)

    return VaultStats(
        vault=vault,
        idea_id=idea_id,
        papers=len(papers),
        knowledge_pages=len(knowledge),
        relation_maps=1,
        linked_files=linked_files,
        total_markdown=len(markdown_files),
        total_wikilinks=total_links,
    )


def update_global_readme(root: Path, stats: list[VaultStats], dry_run: bool) -> None:
    readme = root / "README.md"
    if not readme.exists():
        return
    lines = [
        "<!-- RELATION-MAPS-START -->",
        "",
        "## Relation Maps",
        "",
        "Each idea vault has an internal Obsidian graph hub.",
    ]
    for item in sorted(stats, key=lambda value: value.idea_id):
        rel = f"{item.vault.name}/wiki/relations/{item.idea_id}-relation-map.md"
        lines.append(f"- {item.idea_id}: [{item.vault.name} relation map]({rel})")
    lines.append("<!-- RELATION-MAPS-END -->")
    text = upsert_marker(read_text(readme), "RELATION-MAPS", "\n".join(lines))
    write_text(readme, text, dry_run)


def select_vaults(root: Path, requested: list[str]) -> list[Path]:
    if requested:
        result = []
        for value in requested:
            path = Path(value).expanduser()
            if not path.is_absolute():
                path = root / value
            result.append(path)
        return result
    return sorted(path for path in root.glob("Postgraduate_*") if path.is_dir())


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Obsidian relation maps inside Postgraduate vaults.")
    parser.add_argument("--root", default="~/auto-research", help="Root containing Postgraduate_* vaults.")
    parser.add_argument("--vault", action="append", default=[], help="Specific vault path or name; may be repeated.")
    parser.add_argument("--date", default=date.today().isoformat(), help="Date written to frontmatter/logs.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned stats without writing files.")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    stats: list[VaultStats] = []
    for vault in select_vaults(root, args.vault):
        item = process_vault(vault.expanduser().resolve(), args.date, args.dry_run)
        if item:
            stats.append(item)

    update_global_readme(root, stats, args.dry_run)

    for item in stats:
        print(
            f"{item.vault.name}\t{item.idea_id}\t"
            f"papers={item.papers}\tknowledge={item.knowledge_pages}\t"
            f"linked_files={item.linked_files}/{item.total_markdown}\t"
            f"wikilinks={item.total_wikilinks}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
