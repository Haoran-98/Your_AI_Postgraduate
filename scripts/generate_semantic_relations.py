#!/usr/bin/env python3
"""Generate deterministic semantic relation clusters inside Postgraduate vaults."""

from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


MARKER_SEMANTIC = "SEMANTIC-RELATIONS"
MARKER_SEMANTIC_LAYER = "SEMANTIC-LAYER"


STOP_DATASET_VALUES = {
    "",
    "unknown",
    "none",
    "n/a",
    "not found",
    "metadata pass did not expose",
    "unknown; infer from paper if deep-read confirms",
}


METHOD_PATTERNS: dict[str, list[str]] = {
    "large-language-models": [r"\bllm\b", r"large language model", r"\bgpt\b", r"language models?"],
    "transformer-bert-roberta": [r"\btransformer", r"\bbert\b", r"\broberta\b", r"\bdeberta\b"],
    "prompting-reasoning": [r"prompt", r"chain[- ]of[- ]thought", r"\bcot\b", r"reasoning"],
    "retrieval-augmented-generation": [r"\brag\b", r"retrieval[- ]augmented", r"retrieve"],
    "causal-discovery": [r"causal discovery", r"discover(?:y|ing) caus", r"causal graph"],
    "causal-inference-scm-dag": [r"causal inference", r"structural causal", r"\bscm\b", r"\bdag\b", r"do-calculus"],
    "knowledge-graph": [r"knowledge graph", r"\bkg\b", r"graph embedding"],
    "graph-neural-network": [r"graph neural", r"\bgnn\b", r"\bgcn\b", r"\bgat\b"],
    "agent-based-simulation": [r"agent[- ]based", r"multi[- ]agent", r"simulation", r"simulat"],
    "reinforcement-learning": [r"reinforcement learning", r"\brl\b", r"policy learning"],
    "machine-learning-classification": [r"machine learning", r"classif", r"regression", r"random forest", r"\bsvm\b", r"logistic"],
    "deep-learning": [r"deep learning", r"\bcnn\b", r"\blstm\b", r"\brnn\b", r"neural network"],
    "multimodal-sensing": [r"multimodal", r"multi[- ]modal", r"sensor"],
    "eeg-signal-analysis": [r"\beeg\b", r"electroencephal"],
    "fnirs-signal-analysis": [r"\bfnirs\b", r"near[- ]infrared", r"\bnirs\b"],
    "physiological-signals": [r"\becg\b", r"\bgsr\b", r"\beda\b", r"\bhrv\b", r"heart rate", r"pupillometry", r"eye[- ]tracking"],
    "benchmark-dataset-construction": [r"benchmark", r"dataset construction", r"corpus", r"data set"],
    "network-analysis": [r"network analysis", r"social network", r"epistemic network"],
    "topic-stance-sentiment-modeling": [r"topic model", r"stance", r"sentiment", r"ideolog"],
}


VARIABLE_PATTERNS: dict[str, list[str]] = {
    "cognitive-load-workload": [r"cognitive load", r"mental workload", r"\bworkload\b"],
    "stress": [r"\bstress\b", r"acute stress"],
    "fatigue-burnout": [r"fatigue", r"burnout", r"security fatigue"],
    "attention-vigilance": [r"attention", r"vigilance", r"distraction", r"inattention"],
    "situation-awareness": [r"situation awareness", r"situational awareness"],
    "trust-calibration": [r"trust", r"calibrat"],
    "performance": [r"performance", r"human performance", r"task performance"],
    "personality-demographics": [r"personality", r"demographic", r"big five", r"mbti"],
    "belief-ideology-stance": [r"belief", r"ideology", r"stance", r"opinion"],
    "misinformation-credibility": [r"misinformation", r"disinformation", r"credibility", r"fake news"],
    "bias-fairness": [r"\bbias\b", r"fairness", r"stereotype"],
    "group-collaboration": [r"group", r"collaborat", r"team", r"community"],
    "learning-engagement": [r"learning", r"engagement", r"student"],
    "emotion-affect": [r"emotion", r"affect", r"mood"],
    "causal-reasoning-ability": [r"causal reasoning", r"causal capabilit", r"counterfactual"],
}


MECHANISM_PATTERNS: dict[str, list[str]] = {
    "automation-complacency-and-skill-decay": [r"automation", r"complacency", r"manual skill", r"decision aid"],
    "workload-stress-performance-pathway": [r"workload", r"stress", r"performance"],
    "fatigue-attention-degradation": [r"fatigue", r"attention", r"degrad", r"distraction"],
    "trust-calibration-human-ai-reliance": [r"trust", r"automation", r"reliance", r"calibrat"],
    "multimodal-physiology-to-cognitive-state": [r"\beeg\b|\bfnirs\b|\becg\b|\bgsr\b|\beda\b|\bhrv\b", r"cognitive|workload|stress|fatigue"],
    "text-to-psychological-profile": [r"text", r"personality|demographic|profile|author"],
    "social-diffusion-opinion-dynamics": [r"social", r"diffusion|spread|cascade|opinion"],
    "knowledge-graph-to-group-cognition": [r"knowledge graph|network", r"group|collaborat|community"],
    "causal-graph-to-llm-reasoning": [r"causal graph|structural causal|dag|scm", r"llm|language model|reasoning"],
    "data-bias-feedback-loop": [r"bias", r"feedback loop|training data|model output|scientific"],
    "agent-environment-adaptation": [r"agent", r"environment", r"adapt|planning|simulation"],
    "benchmark-to-evaluation-loop": [r"benchmark|dataset", r"evaluat|metric|assessment"],
}


DATASET_PATTERNS: dict[str, list[str]] = {
    "reddit-data": [r"\breddit\b", r"pandora"],
    "twitter-x-data": [r"\btwitter\b", r"\bx data\b", r"tweets?"],
    "news-fact-checking-data": [r"\bliar\b", r"\bfever\b", r"fake news", r"fact[- ]check"],
    "physiological-sensor-data": [r"\beeg\b|\bfnirs\b|\becg\b|\bgsr\b|\beda\b|\bhrv\b|pupillometry|eye[- ]tracking"],
    "simulation-environment-data": [r"simulation", r"environment", r"virtual reality", r"\bvr\b"],
    "education-learning-analytics-data": [r"learning analytics", r"student", r"classroom", r"mooc"],
    "llm-causal-benchmark-data": [r"causal benchmark", r"causal reasoning", r"counterfactual", r"llm"],
}


@dataclass
class Paper:
    paper_id: str
    title: str
    path: Path
    fields: dict[str, str] = field(default_factory=dict)
    text: str = ""
    datasets: set[str] = field(default_factory=set)
    methods: set[str] = field(default_factory=set)
    variables: set[str] = field(default_factory=set)
    mechanisms: set[str] = field(default_factory=set)

    @property
    def link(self) -> str:
        return f"[[{self.path.stem}|{self.paper_id} {self.title.replace('|', '/')}]]"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def write_text(path: Path, text: str, dry_run: bool) -> None:
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def update_date(text: str, today: str) -> str:
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


def h1(path: Path) -> str:
    for line in read_text(path).splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def strip_generated_blocks(text: str) -> str:
    for marker in (MARKER_SEMANTIC, "OBSIDIAN-RELATIONS"):
        start = f"<!-- {marker}-START -->"
        end = f"<!-- {marker}-END -->"
        text = re.sub(rf"\n?{re.escape(start)}.*?{re.escape(end)}\n?", "\n", text, flags=re.S)
    return text


def markdown_section(text: str, heading: str) -> str:
    text = strip_generated_blocks(text)
    start = text.find(heading)
    if start < 0:
        return ""
    next_heading = text.find("\n## ", start + len(heading))
    return text[start:] if next_heading < 0 else text[start:next_heading]


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


def first(wiki: Path, subdir: str, pattern: str) -> Path | None:
    folder = wiki / subdir
    if not folder.exists():
        return None
    matches = sorted(folder.glob(pattern))
    return matches[0] if matches else None


def load_master_rows(wiki: Path, idea_id: str) -> dict[str, dict[str, str]]:
    path = first(wiki, "papers", f"{idea_id}-paper-master.csv")
    if not path:
        return {}
    rows: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        for row in csv.DictReader(handle):
            paper_id = (row.get("id") or row.get("paper_id") or "").strip()
            if paper_id:
                rows[paper_id] = {key: (value or "").strip() for key, value in row.items()}
    return rows


def load_papers(wiki: Path, idea_id: str) -> list[Paper]:
    rows = load_master_rows(wiki, idea_id)
    papers: list[Paper] = []
    folder = wiki / "papers"
    if not folder.exists():
        return papers
    for path in sorted(folder.glob("P*.md")):
        paper_id = path.name.split("-", 1)[0]
        text = read_text(path)
        title = rows.get(paper_id, {}).get("title") or h1(path)
        paper = Paper(paper_id=paper_id, title=title, path=path, fields=rows.get(paper_id, {}), text=text)
        papers.append(paper)
    return papers


def text_blob(paper: Paper) -> str:
    useful_fields = [
        "title",
        "venue",
        "type",
        "cluster",
        "dataset",
        "method",
        "finding",
    ]
    paper_knowledge = "\n".join(
        line for line in markdown_section(paper.text, "## 论文知识").splitlines() if not line.lstrip().startswith("- Limitation:")
    )
    basic_info = markdown_section(paper.text, "## 基本信息")
    parts = [paper.title, basic_info, paper_knowledge]
    parts.extend(paper.fields.get(key, "") for key in useful_fields)
    return "\n".join(parts).lower()


def pattern_hits(blob: str, patterns: dict[str, list[str]], require_all: bool = False) -> set[str]:
    hits: set[str] = set()
    for label, regexes in patterns.items():
        matcher = all if require_all else any
        if matcher(re.search(regex, blob, flags=re.I) for regex in regexes):
            hits.add(label)
    return hits


def normalize_dataset_name(value: str) -> str:
    value = value.strip().strip("。.;,")
    value = re.sub(r"\s+", " ", value)
    lowered = value.lower()
    if lowered in STOP_DATASET_VALUES or "infer from paper" in lowered:
        return ""
    return value[:80]


def extract_explicit_dataset(paper: Paper) -> set[str]:
    values: set[str] = set()
    for key in ("dataset", "dataset_url"):
        raw = paper.fields.get(key, "")
        if not raw:
            continue
        for part in re.split(r";|\||,", raw):
            normalized = normalize_dataset_name(part)
            if normalized:
                if normalized.startswith("http"):
                    host = re.sub(r"^https?://", "", normalized).split("/", 1)[0]
                    values.add(f"dataset-host:{host}")
                else:
                    values.add(normalized)
    return values


def assign_semantics(papers: list[Paper]) -> None:
    for paper in papers:
        blob = text_blob(paper)
        paper.datasets = extract_explicit_dataset(paper) | pattern_hits(blob, DATASET_PATTERNS)
        paper.methods = pattern_hits(blob, METHOD_PATTERNS)
        paper.variables = pattern_hits(blob, VARIABLE_PATTERNS)
        paper.mechanisms = pattern_hits(blob, MECHANISM_PATTERNS, require_all=True)


def clusters(papers: list[Paper], attr: str, minimum: int) -> dict[str, list[Paper]]:
    result: dict[str, list[Paper]] = defaultdict(list)
    for paper in papers:
        for label in sorted(getattr(paper, attr)):
            result[label].append(paper)
    return {key: value for key, value in sorted(result.items()) if len(value) >= minimum}


def semantic_link_stem(idea_id: str, kind: str) -> str:
    return f"{idea_id}-semantic-{kind}-clusters"


def render_cluster_page(
    domain: str,
    idea_id: str,
    kind: str,
    title: str,
    cluster_map: dict[str, list[Paper]],
    semantic_map_stem: str,
    today: str,
) -> str:
    lines = [
        "---",
        f"type: semantic-{kind}",
        f"domain: {domain}",
        "status: heuristic",
        f"updated: {today}",
        f"idea_id: {idea_id}",
        "tags: [postgraduate, semantic-relations, heuristic-cluster]",
        "---",
        "",
        f"# {title}",
        "",
        "本页由规则脚本从 paper master、paper card 与已抽取知识页中自动生成，用于导航和批量复核；不是 PDF 精读后的最终事实表。",
        "",
        f"- 语义总图: [[{semantic_map_stem}]]",
        "",
    ]
    if not cluster_map:
        lines.append("暂无达到阈值的共享语义簇。")
    for label, items in cluster_map.items():
        lines.extend([f"## {label}", "", f"- papers: {len(items)}"])
        lines.append("- members: " + "、".join(paper.link for paper in items))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def similarity_edges(papers: list[Paper], top_k: int) -> list[tuple[float, Paper, Paper, set[str]]]:
    edges: list[tuple[float, Paper, Paper, set[str]]] = []
    for i, left in enumerate(papers):
        left_features = left.datasets | left.methods | left.variables | left.mechanisms
        if not left_features:
            continue
        for right in papers[i + 1 :]:
            right_features = right.datasets | right.methods | right.variables | right.mechanisms
            if not right_features:
                continue
            shared = left_features & right_features
            if not shared:
                continue
            score = len(shared) / len(left_features | right_features)
            edges.append((score, left, right, shared))
    edges.sort(key=lambda item: (-item[0], item[1].paper_id, item[2].paper_id))
    return edges[:top_k]


def render_edges_page(domain: str, idea_id: str, edges: list[tuple[float, Paper, Paper, set[str]]], semantic_map_stem: str, today: str) -> str:
    lines = [
        "---",
        "type: semantic-paper-similarity",
        f"domain: {domain}",
        "status: heuristic",
        f"updated: {today}",
        f"idea_id: {idea_id}",
        "tags: [postgraduate, semantic-relations, paper-similarity]",
        "---",
        "",
        f"# {idea_id} Paper Similarity Edges",
        "",
        "本页列出基于共享数据集、方法、变量和机制标签的论文相似边，用于发现可合并阅读、对照实验或综述段落组织线索。",
        "",
        f"- 语义总图: [[{semantic_map_stem}]]",
        "",
    ]
    if not edges:
        lines.append("暂无可生成的相似边。")
    for score, left, right, shared in edges:
        labels = ", ".join(sorted(shared))
        lines.append(f"- {left.link} <-> {right.link} | score={score:.2f} | shared={labels}")
    return "\n".join(lines).rstrip() + "\n"


def render_semantic_map(
    domain: str,
    idea_id: str,
    core_relation_map: Path | None,
    pages: dict[str, Path],
    counts: dict[str, int],
    today: str,
) -> str:
    lines = [
        "---",
        "type: semantic-relation-map",
        f"domain: {domain}",
        "status: heuristic",
        f"updated: {today}",
        f"idea_id: {idea_id}",
        "tags: [postgraduate, semantic-relations, obsidian-graph]",
        "---",
        "",
        f"# {idea_id} 语义关系图",
        "",
        "本页是该 vault 内部的语义聚类入口。它把论文之间共享的数据集、方法、变量、因果机制和相似边整理为 Obsidian 可导航节点。",
        "",
        "## 入口",
    ]
    if core_relation_map:
        lines.append(f"- 结构关系图: [[{core_relation_map.stem}]]")
    for label, path in pages.items():
        lines.append(f"- {label}: [[{path.stem}]]")
    lines.extend(["", "## 聚类规模"])
    for label, count in counts.items():
        lines.append(f"- {label}: {count}")
    lines.extend(
        [
            "",
            "## 使用边界",
            "- 本层是自动语义导航层，基于元数据、摘要片段、paper card 和已抽取知识页的规则匹配。",
            "- `unknown` 或未命中的语义项不代表论文没有对应数据/方法/机制，只代表本轮自动抽取没有可靠识别。",
            "- 做实验设计、引用论证或综述定稿前，需要回到 paper card、PDF 和 artifact 页面复核。",
            "",
        ]
    )
    return "\n".join(lines)


def paper_semantic_section(paper: Paper, pages: dict[str, Path]) -> str:
    def fmt(values: set[str]) -> str:
        return ", ".join(sorted(values)) if values else "none-detected"

    lines = [
        f"<!-- {MARKER_SEMANTIC}-START -->",
        "",
        "## 语义关系",
        f"- shared_datasets: {fmt(paper.datasets)}",
        f"- shared_methods: {fmt(paper.methods)}",
        f"- shared_variables: {fmt(paper.variables)}",
        f"- shared_mechanisms: {fmt(paper.mechanisms)}",
    ]
    for label, path in pages.items():
        lines.append(f"- {label}: [[{path.stem}]]")
    lines.append(f"<!-- {MARKER_SEMANTIC}-END -->")
    return "\n".join(lines)


def update_relation_entries(wiki: Path, semantic_map: Path, idea_id: str, today: str, dry_run: bool) -> None:
    relation_map = first(wiki, "relations", f"{idea_id}-relation-map.md")
    if relation_map:
        section = f"""<!-- {MARKER_SEMANTIC_LAYER}-START -->

## Semantic Layer
- Semantic relation map: [[{semantic_map.stem}]]
- Contains heuristic clusters for shared datasets, methods, variables, mechanisms, and paper similarity edges.
<!-- {MARKER_SEMANTIC_LAYER}-END -->"""
        text = update_date(upsert_marker(read_text(relation_map), MARKER_SEMANTIC_LAYER, section), today)
        write_text(relation_map, text, dry_run)

    for name in ("index.md", "hot.md"):
        path = wiki / name
        if not path.exists():
            continue
        section = f"""<!-- {MARKER_SEMANTIC_LAYER}-START -->

## Semantic Layer
- Semantic relation map: [[{semantic_map.stem}]]
- Use it to navigate paper clusters by shared datasets, methods, variables, mechanisms, and similarity edges.
<!-- {MARKER_SEMANTIC_LAYER}-END -->"""
        text = update_date(upsert_marker(read_text(path), MARKER_SEMANTIC_LAYER, section), today)
        write_text(path, text, dry_run)

    log = wiki / "log.md"
    if log.exists():
        line = f"- {today}: Generated or refreshed semantic relation clusters for {idea_id}."
        text = read_text(log)
        if line not in text:
            if text and not text.endswith("\n"):
                text += "\n"
            text += "\n## Semantic Relation Update\n" + line + "\n"
        text = update_date(text, today)
        write_text(log, text, dry_run)


def process_vault(vault: Path, today: str, dry_run: bool, minimum: int, top_edges: int) -> dict[str, int | str] | None:
    wiki = vault / "wiki"
    if not wiki.exists():
        return None
    detected = idea_id_from_vault(wiki)
    if not detected:
        return None
    idea_id, _idea_card = detected
    domain = vault.name.removeprefix("Postgraduate_")
    papers = load_papers(wiki, idea_id)
    if not papers:
        return None
    assign_semantics(papers)

    semantic_dir = wiki / "relations" / "semantic"
    semantic_map = semantic_dir / f"{idea_id}-semantic-map.md"
    pages = {
        "数据集簇": semantic_dir / f"{semantic_link_stem(idea_id, 'dataset')}.md",
        "方法簇": semantic_dir / f"{semantic_link_stem(idea_id, 'method')}.md",
        "变量簇": semantic_dir / f"{semantic_link_stem(idea_id, 'variable')}.md",
        "机制簇": semantic_dir / f"{semantic_link_stem(idea_id, 'mechanism')}.md",
        "论文相似边": semantic_dir / f"{idea_id}-semantic-paper-similarity-edges.md",
    }

    dataset_clusters = clusters(papers, "datasets", minimum)
    method_clusters = clusters(papers, "methods", minimum)
    variable_clusters = clusters(papers, "variables", minimum)
    mechanism_clusters = clusters(papers, "mechanisms", minimum)
    edges = similarity_edges(papers, top_edges)

    semantic_map_text = render_semantic_map(
        domain,
        idea_id,
        first(wiki, "relations", f"{idea_id}-relation-map.md"),
        pages,
        {
            "dataset_clusters": len(dataset_clusters),
            "method_clusters": len(method_clusters),
            "variable_clusters": len(variable_clusters),
            "mechanism_clusters": len(mechanism_clusters),
            "similarity_edges": len(edges),
        },
        today,
    )
    write_text(semantic_map, semantic_map_text, dry_run)
    write_text(pages["数据集簇"], render_cluster_page(domain, idea_id, "dataset", f"{idea_id} Shared Dataset Clusters", dataset_clusters, semantic_map.stem, today), dry_run)
    write_text(pages["方法簇"], render_cluster_page(domain, idea_id, "method", f"{idea_id} Shared Method Clusters", method_clusters, semantic_map.stem, today), dry_run)
    write_text(pages["变量簇"], render_cluster_page(domain, idea_id, "variable", f"{idea_id} Shared Variable Clusters", variable_clusters, semantic_map.stem, today), dry_run)
    write_text(pages["机制簇"], render_cluster_page(domain, idea_id, "mechanism", f"{idea_id} Shared Mechanism Clusters", mechanism_clusters, semantic_map.stem, today), dry_run)
    write_text(pages["论文相似边"], render_edges_page(domain, idea_id, edges, semantic_map.stem, today), dry_run)

    compact_pages = {"语义总图": semantic_map, **pages}
    for paper in papers:
        text = update_date(upsert_marker(read_text(paper.path), MARKER_SEMANTIC, paper_semantic_section(paper, compact_pages)), today)
        write_text(paper.path, text, dry_run)

    update_relation_entries(wiki, semantic_map, idea_id, today, dry_run)

    return {
        "vault": vault.name,
        "idea_id": idea_id,
        "papers": len(papers),
        "dataset_clusters": len(dataset_clusters),
        "method_clusters": len(method_clusters),
        "variable_clusters": len(variable_clusters),
        "mechanism_clusters": len(mechanism_clusters),
        "similarity_edges": len(edges),
    }


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
    parser = argparse.ArgumentParser(description="Generate heuristic semantic clusters inside Postgraduate vaults.")
    parser.add_argument("--root", default="~/auto-research", help="Root containing Postgraduate_* vaults.")
    parser.add_argument("--vault", action="append", default=[], help="Specific vault path or name; may be repeated.")
    parser.add_argument("--date", default=date.today().isoformat(), help="Date written to frontmatter/logs.")
    parser.add_argument("--min-cluster-size", type=int, default=2, help="Minimum paper count for a semantic cluster.")
    parser.add_argument("--top-edges", type=int, default=80, help="Maximum paper similarity edges per vault.")
    parser.add_argument("--dry-run", action="store_true", help="Compute and print stats without writing files.")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    stats = []
    for vault in select_vaults(root, args.vault):
        item = process_vault(vault.expanduser().resolve(), args.date, args.dry_run, args.min_cluster_size, args.top_edges)
        if item:
            stats.append(item)

    for item in stats:
        print(
            f"{item['vault']}\t{item['idea_id']}\tpapers={item['papers']}\t"
            f"datasets={item['dataset_clusters']}\tmethods={item['method_clusters']}\t"
            f"variables={item['variable_clusters']}\tmechanisms={item['mechanism_clusters']}\t"
            f"edges={item['similarity_edges']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
