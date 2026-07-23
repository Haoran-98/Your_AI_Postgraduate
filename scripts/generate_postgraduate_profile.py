#!/usr/bin/env python3
"""Generate a deterministic knowledge and task-fit profile for one vault."""

from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


DIMENSION_LABELS = {
    "literature_foundation": {"en": "Literature foundation", "zh": "文献基础"},
    "evidence_grounding": {"en": "Evidence grounding", "zh": "证据扎根"},
    "method_empirical": {"en": "Method and empirical knowledge", "zh": "方法与实证知识"},
    "causal_reasoning": {"en": "Causal reasoning", "zh": "因果推理"},
    "synthesis_innovation": {"en": "Synthesis and innovation", "zh": "综合与创新"},
    "retrieval_readiness": {"en": "Retrieval readiness", "zh": "检索就绪度"},
}

TASKS = [
    {
        "key": "rag_research",
        "title": {"en": "Evidence-grounded RAG research", "zh": "证据扎根的 RAG 科研问答"},
        "weights": {
            "retrieval_readiness": 0.40,
            "evidence_grounding": 0.30,
            "literature_foundation": 0.20,
            "synthesis_innovation": 0.10,
        },
        "core_dimension": "retrieval_readiness",
    },
    {
        "key": "knowledge_graph",
        "title": {"en": "Knowledge-graph curation", "zh": "知识图谱整理与维护"},
        "weights": {
            "causal_reasoning": 0.35,
            "retrieval_readiness": 0.30,
            "evidence_grounding": 0.25,
            "synthesis_innovation": 0.10,
        },
        "core_dimension": "causal_reasoning",
    },
    {
        "key": "literature_synthesis",
        "title": {"en": "Literature synthesis and survey writing", "zh": "文献综合与综述写作"},
        "weights": {
            "literature_foundation": 0.35,
            "evidence_grounding": 0.30,
            "synthesis_innovation": 0.25,
            "retrieval_readiness": 0.10,
        },
        "core_dimension": "literature_foundation",
    },
    {
        "key": "causal_hypotheses",
        "title": {"en": "Causal mechanism and hypothesis development", "zh": "因果机制与假设提出"},
        "weights": {
            "causal_reasoning": 0.40,
            "synthesis_innovation": 0.25,
            "evidence_grounding": 0.25,
            "method_empirical": 0.10,
        },
        "core_dimension": "causal_reasoning",
    },
    {
        "key": "experiment_design",
        "title": {"en": "Experiment and evaluation design", "zh": "实验与评估设计"},
        "weights": {
            "method_empirical": 0.40,
            "evidence_grounding": 0.25,
            "causal_reasoning": 0.20,
            "literature_foundation": 0.15,
        },
        "core_dimension": "method_empirical",
    },
    {
        "key": "dataset_benchmark",
        "title": {"en": "Dataset and benchmark construction", "zh": "数据集与基准构建"},
        "weights": {
            "method_empirical": 0.45,
            "retrieval_readiness": 0.25,
            "evidence_grounding": 0.20,
            "synthesis_innovation": 0.10,
        },
        "core_dimension": "method_empirical",
    },
]

KNOWLEDGE_DIRS = [
    "variables",
    "mechanisms",
    "datasets",
    "claims",
    "hypotheses",
    "gaps",
    "causal-bridges",
    "causal-core",
    "surveys",
    "experiments",
    "relations",
]


def clamp(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 1)


def saturation(value: int, target: int) -> float:
    if target <= 0:
        return 0.0
    return min(value / target, 1.0) * 100.0


def ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return min(numerator / denominator, 1.0) * 100.0


def weighted(values: list[tuple[float, float]]) -> float:
    return clamp(sum(value * weight for value, weight in values))


def frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}
    try:
        value = yaml.safe_load(text[4:end]) or {}
    except yaml.YAMLError:
        return {}
    return value if isinstance(value, dict) else {}


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def jsonl_summary(path: Path) -> tuple[int, Counter[str], Counter[str]]:
    count = 0
    source_types: Counter[str] = Counter()
    evidence_levels: Counter[str] = Counter()
    if not path.exists():
        return count, source_types, evidence_levels
    with path.open(encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            count += 1
            metadata = item.get("metadata") or {}
            source_types[str(metadata.get("source_type") or "unknown")] += 1
            evidence_levels[str(metadata.get("rag_evidence_level") or "unknown")] += 1
    return count, source_types, evidence_levels


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open(encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            try:
                json.loads(line)
            except json.JSONDecodeError:
                continue
            count += 1
    return count


def markdown_count(path: Path, recursive: bool = False) -> int:
    if not path.exists():
        return 0
    pattern = "**/*.md" if recursive else "*.md"
    return sum(1 for item in path.glob(pattern) if item.is_file())


def domain_name(vault: Path) -> str:
    value = vault.name.removeprefix("Postgraduate_").replace("_", " ")
    return value or vault.name


def registered_research_lines(wiki: Path) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    folder = wiki / "research-lines"
    if not folder.exists():
        return result
    for path in sorted(folder.glob("*.md")):
        metadata = frontmatter(path)
        if metadata.get("type") != "research-line":
            continue
        title = path.stem.replace("-", " ").title()
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("# "):
                title = line[2:].removeprefix("Research Line:").strip()
                break
        result.append({
            "key": str(metadata.get("research_line") or path.stem),
            "title": title,
            "idea_id": str(metadata.get("idea_id") or ""),
            "status": str(metadata.get("status") or "unknown"),
            "path": f"wiki/research-lines/{path.name}",
        })
    return result


def readiness_level(score: float, language: str, core_score: float | None = None) -> str:
    if score >= 80 and (core_score is None or core_score >= 80):
        return "ready now" if language == "en" else "当前可重点承担"
    if score >= 60:
        return "suitable with targeted review" if language == "en" else "适合在针对性复核后承担"
    return "needs more evidence" if language == "en" else "仍需补充证据"


def build_profile(vault: Path, language: str = "en") -> dict[str, Any]:
    wiki = vault / "wiki"
    rag = vault / "rag"
    memory_root = rag / "paper-memory"
    research_lines = registered_research_lines(wiki)

    cards = sorted((wiki / "papers").glob("P*.md")) if (wiki / "papers").exists() else []
    statuses: Counter[str] = Counter()
    evidence_levels: Counter[str] = Counter()
    venues: set[str] = set()
    for card in cards:
        metadata = frontmatter(card)
        statuses[str(metadata.get("status") or "unknown")] += 1
        evidence_levels[str(metadata.get("evidence_level") or "unknown")] += 1
        venue = str(metadata.get("venue") or metadata.get("source") or "").strip()
        if venue and not venue.startswith("http"):
            venues.add(venue.casefold())

    kind_counts: Counter[str] = Counter()
    evidence_match_counts: Counter[str] = Counter()
    review_counts: Counter[str] = Counter()
    causal_status_counts: Counter[str] = Counter()
    entity_counts: Counter[str] = Counter()
    entity_display: dict[str, str] = {}
    memory_files = sorted((memory_root / "papers").glob("P*.json")) if (memory_root / "papers").exists() else []
    validated_memories = 0
    for memory_file in memory_files:
        wrapper = read_json(memory_file)
        for memory in wrapper.get("validated_memories") or []:
            if not isinstance(memory, dict):
                continue
            validated_memories += 1
            kind_counts[str(memory.get("kind") or "unknown")] += 1
            evidence_match_counts[str(memory.get("evidence_match") or "unknown")] += 1
            review_counts[str(memory.get("review_status") or "unknown")] += 1
            causal_status_counts[str(memory.get("causal_status") or "none")] += 1
            for entity in memory.get("entities") or []:
                display = re.sub(r"\s+", " ", str(entity)).strip()
                key = display.casefold()
                if len(display) < 2 or display.isdigit():
                    continue
                entity_counts[key] += 1
                entity_display.setdefault(key, display)

    top_entities = [
        {"name": entity_display[key], "count": count}
        for key, count in sorted(entity_counts.items(), key=lambda item: (-item[1], entity_display[item[0]].casefold()))[:15]
    ]

    page_counts = {name: markdown_count(wiki / name, recursive=name in {"causal-core", "relations"}) for name in KNOWLEDGE_DIRS}
    knowledge_pages = sum(page_counts.values())
    causal_edges = count_jsonl(memory_root / "causal-edges.jsonl")
    memory_corpus_records = count_jsonl(memory_root / "corpus.jsonl")
    rag_records, source_type_counts, rag_evidence_counts = jsonl_summary(rag / "corpus.jsonl")

    paper_count = len(cards)
    fulltext_read = statuses["fulltext-read"]
    blocked = min(max(statuses["fulltext-blocked"], evidence_levels["blocked"]), paper_count)
    memory_papers = len(memory_files)
    matched_memories = evidence_match_counts["exact"] + evidence_match_counts["layout-recovered"]
    reviewed_memories = review_counts["machine-reviewed"] + review_counts["human-verified"]
    causal_memories = sum(count for key, count in causal_status_counts.items() if key not in {"", "none", "unknown"})
    mechanism_variable_memories = kind_counts["mechanism"] + kind_counts["variable"]
    synthesis_memories = kind_counts["transferable_principle"] + kind_counts["contradiction"] + kind_counts["open_question"]
    required_method_kinds = {"study_design", "experiment", "dataset", "variable", "finding", "limitation"}
    method_kind_coverage = ratio(sum(1 for key in required_method_kinds if kind_counts[key] > 0), len(required_method_kinds))
    synthesis_pages = sum(page_counts[name] for name in ["surveys", "claims", "hypotheses", "gaps", "causal-bridges"])
    causal_pages = page_counts["variables"] + page_counts["mechanisms"] + page_counts["causal-bridges"] + page_counts["causal-core"]
    empirical_pages = page_counts["datasets"] + page_counts["experiments"]

    components = {
        "literature_foundation": {
            "paper_volume": saturation(paper_count, 50),
            "verified_fulltext_coverage": ratio(fulltext_read, paper_count),
            "paper_memory_coverage": ratio(memory_papers, max(fulltext_read, paper_count)),
            "venue_diversity": saturation(len(venues), 10),
        },
        "evidence_grounding": {
            "reviewed_memory_ratio": ratio(reviewed_memories, validated_memories),
            "matched_evidence_ratio": ratio(matched_memories, validated_memories),
            "validated_memory_volume": saturation(validated_memories, 500),
            "non_blocked_coverage": ratio(max(paper_count - blocked, 0), paper_count),
        },
        "method_empirical": {
            "method_kind_coverage": method_kind_coverage,
            "experiment_memory_volume": saturation(kind_counts["experiment"], 50),
            "dataset_memory_volume": saturation(kind_counts["dataset"], 50),
            "durable_empirical_pages": saturation(empirical_pages, 6),
        },
        "causal_reasoning": {
            "causal_memory_volume": saturation(causal_memories, 250),
            "causal_edge_volume": saturation(causal_edges, 200),
            "mechanism_variable_memory": saturation(mechanism_variable_memories, 120),
            "durable_causal_pages": saturation(causal_pages, 10),
        },
        "synthesis_innovation": {
            "synthesis_memory_volume": saturation(synthesis_memories, 200),
            "durable_synthesis_pages": saturation(synthesis_pages, 10),
            "paper_memory_coverage": ratio(memory_papers, max(fulltext_read, paper_count)),
            "relation_pages": saturation(page_counts["relations"], 4),
        },
        "retrieval_readiness": {
            "source_rag_records": saturation(rag_records, 5000),
            "memory_rag_records": saturation(memory_corpus_records, 1000),
            "paper_memory_coverage": ratio(memory_papers, max(fulltext_read, paper_count)),
            "relation_pages": saturation(page_counts["relations"], 4),
        },
    }

    dimensions = {
        "literature_foundation": weighted([
            (components["literature_foundation"]["paper_volume"], 0.30),
            (components["literature_foundation"]["verified_fulltext_coverage"], 0.30),
            (components["literature_foundation"]["paper_memory_coverage"], 0.30),
            (components["literature_foundation"]["venue_diversity"], 0.10),
        ]),
        "evidence_grounding": weighted([
            (components["evidence_grounding"]["reviewed_memory_ratio"], 0.35),
            (components["evidence_grounding"]["matched_evidence_ratio"], 0.25),
            (components["evidence_grounding"]["validated_memory_volume"], 0.25),
            (components["evidence_grounding"]["non_blocked_coverage"], 0.15),
        ]),
        "method_empirical": weighted([
            (components["method_empirical"]["method_kind_coverage"], 0.35),
            (components["method_empirical"]["experiment_memory_volume"], 0.20),
            (components["method_empirical"]["dataset_memory_volume"], 0.20),
            (components["method_empirical"]["durable_empirical_pages"], 0.25),
        ]),
        "causal_reasoning": weighted([
            (components["causal_reasoning"]["causal_memory_volume"], 0.30),
            (components["causal_reasoning"]["causal_edge_volume"], 0.30),
            (components["causal_reasoning"]["mechanism_variable_memory"], 0.20),
            (components["causal_reasoning"]["durable_causal_pages"], 0.20),
        ]),
        "synthesis_innovation": weighted([
            (components["synthesis_innovation"]["synthesis_memory_volume"], 0.30),
            (components["synthesis_innovation"]["durable_synthesis_pages"], 0.35),
            (components["synthesis_innovation"]["paper_memory_coverage"], 0.20),
            (components["synthesis_innovation"]["relation_pages"], 0.15),
        ]),
        "retrieval_readiness": weighted([
            (components["retrieval_readiness"]["source_rag_records"], 0.30),
            (components["retrieval_readiness"]["memory_rag_records"], 0.25),
            (components["retrieval_readiness"]["paper_memory_coverage"], 0.25),
            (components["retrieval_readiness"]["relation_pages"], 0.20),
        ]),
    }

    task_fit = []
    for task in TASKS:
        score = weighted([(dimensions[key], weight) for key, weight in task["weights"].items()])
        core_dimension = task["core_dimension"]
        contributors = sorted(task["weights"], key=lambda key: (-task["weights"][key], key))
        task_fit.append({
            "key": task["key"],
            "title": task["title"][language],
            "score": score,
            "readiness": readiness_level(score, language, dimensions[core_dimension]),
            "core_dimension": {
                "key": core_dimension,
                "label": DIMENSION_LABELS[core_dimension][language],
                "score": dimensions[core_dimension],
            },
            "contributing_dimensions": [
                {"key": key, "label": DIMENSION_LABELS[key][language], "score": dimensions[key], "weight": task["weights"][key]}
                for key in contributors
            ],
        })
    task_fit.sort(key=lambda item: (-item["score"], item["key"]))

    lowest_dimension = min(dimensions, key=lambda key: (dimensions[key], key))
    generated_at = datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": "postgraduate-profile-1.0",
        "generated_at": generated_at,
        "language": language,
        "vault": vault.name,
        "domain": domain_name(vault),
        "counts": {
            "paper_cards": paper_count,
            "fulltext_read": fulltext_read,
            "blocked_papers": blocked,
            "paper_memories": memory_papers,
            "validated_memories": validated_memories,
            "causal_edges": causal_edges,
            "knowledge_pages": knowledge_pages,
            "source_rag_records": rag_records,
            "memory_rag_records": memory_corpus_records,
            "unique_venues": len(venues),
            "research_lines": len(research_lines),
        },
        "paper_statuses": dict(statuses),
        "paper_evidence_levels": dict(evidence_levels),
        "memory_kinds": dict(kind_counts.most_common()),
        "memory_evidence_matches": dict(evidence_match_counts.most_common()),
        "memory_review_statuses": dict(review_counts.most_common()),
        "memory_causal_statuses": dict(causal_status_counts.most_common()),
        "page_counts": page_counts,
        "rag_source_types": dict(source_type_counts.most_common()),
        "rag_evidence_levels": dict(rag_evidence_counts.most_common()),
        "top_entities": top_entities,
        "research_lines": research_lines,
        "dimension_components": components,
        "dimensions": dimensions,
        "task_fit": task_fit,
        "best_fit": task_fit[0] if task_fit else None,
        "lowest_dimension": {
            "key": lowest_dimension,
            "label": DIMENSION_LABELS[lowest_dimension][language],
            "score": dimensions[lowest_dimension],
        },
        "source_paths": [
            {"key": "paper_cards", "path": "wiki/papers", "count": paper_count},
            {"key": "paper_memory", "path": "rag/paper-memory/papers", "count": memory_papers},
            {"key": "causal_edges", "path": "rag/paper-memory/causal-edges.jsonl", "count": causal_edges},
            {"key": "knowledge_pages", "path": "wiki", "count": knowledge_pages},
            {"key": "source_rag", "path": "rag/corpus.jsonl", "count": rag_records},
            {"key": "memory_rag", "path": "rag/paper-memory/corpus.jsonl", "count": memory_corpus_records},
        ],
    }


def markdown_report(profile: dict[str, Any]) -> str:
    language = profile["language"]
    zh = language == "zh"
    dimensions = profile["dimensions"]
    counts = profile["counts"]
    labels = [DIMENSION_LABELS[key][language] for key in dimensions]
    values = [dimensions[key] for key in dimensions]
    best = profile["best_fit"]
    entities = ", ".join(item["name"] for item in profile["top_entities"][:8]) or ("None" if not zh else "暂无")

    source_labels = {
        "paper_cards": "论文卡片" if zh else "Paper cards",
        "paper_memory": "紧凑论文记忆" if zh else "Compact paper memory",
        "causal_edges": "已验证因果边" if zh else "Validated causal edges",
        "knowledge_pages": "语料级知识页" if zh else "Corpus-level knowledge pages",
        "source_rag": "来源 RAG 记录" if zh else "Source RAG records",
        "memory_rag": "记忆 RAG 记录" if zh else "Memory RAG records",
    }
    source_links = {
        "paper_cards": "../papers/",
        "paper_memory": "../../rag/paper-memory/papers/",
        "causal_edges": "../../rag/paper-memory/causal-edges.jsonl",
        "knowledge_pages": "../",
        "source_rag": "../../rag/corpus.jsonl",
        "memory_rag": "../../rag/paper-memory/corpus.jsonl",
    }

    lines = [
        "---",
        "type: postgraduate-profile",
        f"vault: {json.dumps(profile['vault'], ensure_ascii=False)}",
        f"domain: {json.dumps(profile['domain'], ensure_ascii=False)}",
        f"generated_at: {profile['generated_at']}",
        "status: current",
        "tags: [postgraduate, knowledge-profile, visualization, task-fit]",
        "---",
        "",
        f"# {'研究生知识画像' if zh else 'Postgraduate Knowledge Profile'}",
        "",
        f"> {'本画像汇总当前已保存的研究产物，表示现阶段任务准备度，不表示永久能力或科研质量。' if zh else 'This profile summarizes currently stored research artifacts. It measures present task readiness, not permanent ability or research quality.'}",
        "",
        f"## {'概览' if zh else 'Overview'}",
        "",
        f"- {'领域' if zh else 'Domain'}: **{profile['domain']}**",
        f"- {'论文卡片' if zh else 'Paper cards'}: **{counts['paper_cards']}**",
        f"- {'全文已读' if zh else 'Full-text read'}: **{counts['fulltext_read']}**",
        f"- {'有紧凑记忆的论文' if zh else 'Papers with compact memory'}: **{counts['paper_memories']}**",
        f"- {'已验证知识记忆' if zh else 'Validated knowledge memories'}: **{counts['validated_memories']}**",
        f"- {'因果边' if zh else 'Causal edges'}: **{counts['causal_edges']}**",
        f"- {'RAG 记录' if zh else 'RAG records'}: **{counts['source_rag_records'] + counts['memory_rag_records']}**",
        f"- {'研究分支' if zh else 'Research lines'}: **{counts['research_lines']}**",
        "",
        f"## {'研究分支' if zh else 'Research Lines'}",
        "",
        f"| Idea | {'分支' if zh else 'Line'} | {'状态' if zh else 'Status'} |",
        "| --- | --- | --- |",
    ]
    for item in profile["research_lines"]:
        lines.append(f"| {item['idea_id'] or '-'} | [{item['title']}](../../{item['path']}) | {item['status']} |")
    if not profile["research_lines"]:
        lines.append(f"| - | {'尚未登记研究分支' if zh else 'No registered research lines'} | - |")

    lines.extend([
        "",
        f"## {'能力维度可视化' if zh else 'Capability Visualization'}",
        "",
        "```mermaid",
        "xychart-beta",
        f"  x-axis [{', '.join(json.dumps(label, ensure_ascii=False) for label in labels)}]",
        "  y-axis 0 --> 100",
        f"  bar [{', '.join(str(value) for value in values)}]",
        "```",
        "",
        f"| {'维度' if zh else 'Dimension'} | {'分数' if zh else 'Score'} | {'状态' if zh else 'Readiness'} |",
        "| --- | ---: | --- |",
    ])
    for key, score in dimensions.items():
        lines.append(f"| {DIMENSION_LABELS[key][language]} | {score:.1f} | {readiness_level(score, language)} |")

    lines.extend([
        "",
        f"## {'获取了哪些知识' if zh else 'Knowledge Acquired'}",
        "",
        f"| {'知识类型' if zh else 'Knowledge type'} | {'记忆数' if zh else 'Memories'} |",
        "| --- | ---: |",
    ])
    for kind, count in list(profile["memory_kinds"].items())[:20]:
        lines.append(f"| `{kind}` | {count} |")

    lines.extend([
        "",
        f"### {'高频研究实体' if zh else 'Frequent Research Entities'}",
        "",
        entities,
        "",
        f"## {'知识从哪里体现' if zh else 'Where The Knowledge Is Stored'}",
        "",
        f"| {'来源层' if zh else 'Source layer'} | {'数量' if zh else 'Count'} | {'路径' if zh else 'Path'} |",
        "| --- | ---: | --- |",
    ])
    for source in profile["source_paths"]:
        key = source["key"]
        lines.append(f"| {source_labels[key]} | {source['count']} | [{source['path']}]({source_links[key]}) |")

    lines.extend([
        "",
        f"## {'更适合承担什么' if zh else 'Best-Suited Research Tasks'}",
        "",
        f"| {'排名' if zh else 'Rank'} | {'任务' if zh else 'Task'} | {'适配度' if zh else 'Fit'} | {'判断' if zh else 'Assessment'} |",
        "| ---: | --- | ---: | --- |",
    ])
    for index, task in enumerate(profile["task_fit"], 1):
        lines.append(f"| {index} | {task['title']} | {task['score']:.1f} | {task['readiness']} |")

    if best:
        lines.extend([
            "",
            f"**{'首要建议' if zh else 'Primary recommendation'}:** {best['title']} ({best['score']:.1f}/100).",
            "",
            f"**{'领域聚焦信号' if zh else 'Domain focus signals'}:** {entities}.",
            "",
            f"**{'优先补强项' if zh else 'Priority gap'}:** {profile['lowest_dimension']['label']} ({profile['lowest_dimension']['score']:.1f}/100).",
        ])

    lines.extend([
        "",
        f"## {'解释边界' if zh else 'Interpretation Boundaries'}",
        "",
        f"- {'分数来自已保存产物和公开阈值，不调用 LLM。' if zh else 'Scores come from stored artifacts and public thresholds; no LLM is called.'}",
        f"- {'文件数量不能替代论文质量、创新性、实验可行性或人工审查。' if zh else 'Artifact counts do not replace paper quality, novelty, experimental feasibility, or human review.'}",
        f"- {'blocked 论文只计入覆盖状态，不支撑已验证知识。' if zh else 'Blocked papers remain visible in coverage but do not support verified knowledge.'}",
        f"- {'重新生成 RAG 后，本 Markdown 画像可被后续科研问答检索。' if zh else 'After rebuilding RAG, this Markdown profile becomes retrievable in later research queries.'}",
        "",
        f"[{'打开 HTML 可视化' if zh else 'Open the HTML dashboard'}](postgraduate-profile.html) | "
        f"[{'查看机器可读画像' if zh else 'Open the machine-readable profile'}](../../rag/postgraduate-profile.json)",
    ])
    return "\n".join(lines) + "\n"


def html_report(profile: dict[str, Any]) -> str:
    language = profile["language"]
    zh = language == "zh"
    counts = profile["counts"]
    dimensions = profile["dimensions"]
    title = "研究生知识画像" if zh else "Postgraduate Knowledge Profile"
    subtitle = "当前研究产物的知识覆盖、证据基础与任务适配度" if zh else "Knowledge coverage, evidence grounding, and task fit from current research artifacts"

    dimension_rows = "".join(
        f"""<div class="bar-row"><div class="bar-label"><span>{html.escape(DIMENSION_LABELS[key][language])}</span><strong>{score:.1f}</strong></div><div class="track"><div class="fill" style="width:{score:.1f}%"></div></div></div>"""
        for key, score in dimensions.items()
    )
    task_rows = "".join(
        f"""<tr><td>{index}</td><td><strong>{html.escape(task['title'])}</strong></td><td>{task['score']:.1f}</td><td>{html.escape(task['readiness'])}</td></tr>"""
        for index, task in enumerate(profile["task_fit"], 1)
    )
    kind_rows = "".join(
        f"<tr><td><code>{html.escape(kind)}</code></td><td>{count}</td></tr>"
        for kind, count in list(profile["memory_kinds"].items())[:20]
    )
    entity_tags = "".join(
        f'<span class="tag">{html.escape(item["name"])}<small>{item["count"]}</small></span>'
        for item in profile["top_entities"][:15]
    ) or '<span class="muted">No extracted entities</span>'
    source_names = {
        "paper_cards": "论文卡片" if zh else "Paper cards",
        "paper_memory": "紧凑论文记忆" if zh else "Compact paper memory",
        "causal_edges": "已验证因果边" if zh else "Validated causal edges",
        "knowledge_pages": "语料级知识页" if zh else "Corpus-level knowledge pages",
        "source_rag": "来源 RAG" if zh else "Source RAG",
        "memory_rag": "记忆 RAG" if zh else "Memory RAG",
    }
    source_links = {
        "paper_cards": "../papers/",
        "paper_memory": "../../rag/paper-memory/papers/",
        "causal_edges": "../../rag/paper-memory/causal-edges.jsonl",
        "knowledge_pages": "../",
        "source_rag": "../../rag/corpus.jsonl",
        "memory_rag": "../../rag/paper-memory/corpus.jsonl",
    }
    source_rows = "".join(
        f"<tr><td>{html.escape(source_names[item['key']])}</td><td>{item['count']}</td><td><a href=\"{source_links[item['key']]}\"><code>{html.escape(item['path'])}</code></a></td></tr>"
        for item in profile["source_paths"]
    )
    research_line_rows = "".join(
        f'<tr><td>{html.escape(item["idea_id"] or "-")}</td><td><a href="../../{html.escape(item["path"])}"><strong>{html.escape(item["title"])}</strong></a></td><td>{html.escape(item["status"])}</td></tr>'
        for item in profile["research_lines"]
    ) or f'<tr><td>-</td><td>{"尚未登记研究分支" if zh else "No registered research lines"}</td><td>-</td></tr>'
    best = profile["best_fit"] or {"title": "-", "score": 0}
    note = (
        "该建议表示当前产物最支持的任务，不表示永久能力，也不能替代人工科研判断。"
        if zh else
        "This recommendation identifies the task best supported by current artifacts. It does not measure permanent ability or replace human research judgment."
    )

    return f"""<!doctype html>
<html lang="{'zh-CN' if zh else 'en'}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)} - {html.escape(profile['domain'])}</title>
  <style>
    :root {{ --bg:#f4f6f7; --surface:#ffffff; --text:#172126; --muted:#66727a; --line:#d7dee2; --green:#157a6e; --blue:#2867b2; --amber:#a86600; --red:#b33a3a; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--bg); color:var(--text); font:15px/1.55 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    main {{ width:min(1180px,calc(100% - 32px)); margin:0 auto; padding:28px 0 56px; }}
    header {{ border-bottom:1px solid var(--line); padding:4px 0 24px; margin-bottom:24px; }}
    h1 {{ margin:0 0 6px; font-size:30px; letter-spacing:0; }}
    h2 {{ margin:0 0 14px; font-size:19px; letter-spacing:0; }}
    p {{ margin:0; }}
    .muted {{ color:var(--muted); }}
    .meta {{ display:flex; gap:16px; flex-wrap:wrap; margin-top:12px; color:var(--muted); }}
    .grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin-bottom:20px; }}
    .kpi,.panel {{ background:var(--surface); border:1px solid var(--line); border-radius:6px; }}
    .kpi {{ padding:14px; min-height:92px; }}
    .kpi strong {{ display:block; font-size:27px; color:var(--blue); }}
    .kpi span {{ color:var(--muted); }}
    .columns {{ display:grid; grid-template-columns:minmax(0,1.1fr) minmax(0,.9fr); gap:16px; margin-bottom:16px; }}
    .panel {{ padding:18px; overflow:hidden; }}
    .bar-row {{ margin:0 0 14px; }}
    .bar-label {{ display:flex; justify-content:space-between; gap:12px; margin-bottom:5px; }}
    .track {{ height:10px; background:#e7ecef; border-radius:3px; overflow:hidden; }}
    .fill {{ height:100%; background:var(--green); }}
    .recommendation {{ border-left:4px solid var(--amber); padding:14px 16px; background:#fffaf0; margin-bottom:16px; }}
    .recommendation strong {{ color:var(--amber); }}
    table {{ width:100%; border-collapse:collapse; }}
    th,td {{ text-align:left; padding:9px 10px; border-bottom:1px solid var(--line); vertical-align:top; }}
    th {{ color:var(--muted); font-size:13px; }}
    code {{ overflow-wrap:anywhere; }}
    a {{ color:var(--blue); }}
    .tags {{ display:flex; flex-wrap:wrap; gap:7px; }}
    .tag {{ display:inline-flex; align-items:center; gap:7px; padding:4px 7px; border:1px solid var(--line); border-radius:3px; background:#f8fafb; }}
    .tag small {{ color:var(--muted); }}
    .footer-note {{ margin-top:18px; padding-top:16px; border-top:1px solid var(--line); color:var(--muted); }}
    @media (max-width:820px) {{ .grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} .columns {{ grid-template-columns:1fr; }} }}
    @media (max-width:480px) {{ main {{ width:min(100% - 20px,1180px); padding-top:18px; }} .grid {{ grid-template-columns:1fr; }} h1 {{ font-size:24px; }} th,td {{ padding:8px 5px; }} }}
  </style>
</head>
<body>
<main>
  <header>
    <h1>{html.escape(title)}</h1>
    <p class="muted">{html.escape(subtitle)}</p>
    <div class="meta"><span>{'领域' if zh else 'Domain'}: <strong>{html.escape(profile['domain'])}</strong></span><span>{'生成时间' if zh else 'Generated'}: {html.escape(profile['generated_at'])}</span></div>
  </header>

  <section class="grid" aria-label="Knowledge summary">
    <div class="kpi"><strong>{counts['paper_cards']}</strong><span>{'论文卡片' if zh else 'Paper cards'}</span></div>
    <div class="kpi"><strong>{counts['fulltext_read']}</strong><span>{'全文已读' if zh else 'Full-text read'}</span></div>
    <div class="kpi"><strong>{counts['validated_memories']}</strong><span>{'已验证知识记忆' if zh else 'Validated memories'}</span></div>
    <div class="kpi"><strong>{counts['causal_edges']}</strong><span>{'因果边' if zh else 'Causal edges'}</span></div>
  </section>

  <div class="recommendation"><strong>{'首要建议' if zh else 'Primary recommendation'}:</strong> {html.escape(best['title'])} ({best['score']:.1f}/100). <span class="muted">{html.escape(note)}</span></div>

  <section class="panel" style="margin-bottom:16px"><h2>{'研究分支' if zh else 'Research Lines'}</h2><table><thead><tr><th>Idea</th><th>{'分支' if zh else 'Line'}</th><th>{'状态' if zh else 'Status'}</th></tr></thead><tbody>{research_line_rows}</tbody></table></section>

  <section class="columns">
    <div class="panel"><h2>{'能力维度' if zh else 'Capability dimensions'}</h2>{dimension_rows}</div>
    <div class="panel"><h2>{'高频研究实体' if zh else 'Frequent research entities'}</h2><div class="tags">{entity_tags}</div></div>
  </section>

  <section class="panel" style="margin-bottom:16px"><h2>{'任务适配排名' if zh else 'Task-fit ranking'}</h2><table><thead><tr><th>#</th><th>{'任务' if zh else 'Task'}</th><th>{'分数' if zh else 'Score'}</th><th>{'判断' if zh else 'Assessment'}</th></tr></thead><tbody>{task_rows}</tbody></table></section>

  <section class="columns">
    <div class="panel"><h2>{'获取的知识类型' if zh else 'Acquired knowledge types'}</h2><table><thead><tr><th>{'类型' if zh else 'Type'}</th><th>{'数量' if zh else 'Count'}</th></tr></thead><tbody>{kind_rows}</tbody></table></div>
    <div class="panel"><h2>{'知识来源' if zh else 'Knowledge sources'}</h2><table><thead><tr><th>{'来源层' if zh else 'Layer'}</th><th>{'数量' if zh else 'Count'}</th><th>{'路径' if zh else 'Path'}</th></tr></thead><tbody>{source_rows}</tbody></table></div>
  </section>

  <p class="footer-note">{'优先补强项' if zh else 'Priority gap'}: <strong>{html.escape(profile['lowest_dimension']['label'])}</strong> ({profile['lowest_dimension']['score']:.1f}/100). <a href="postgraduate-profile.md">Markdown</a> · <a href="../../rag/postgraduate-profile.json">JSON</a></p>
</main>
</body>
</html>
"""


def upsert_marker(path: Path, marker: str, section: str) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8", errors="ignore")
    start = f"<!-- {marker}-START -->"
    end = f"<!-- {marker}-END -->"
    replacement = f"{start}\n{section.strip()}\n{end}"
    if start in text and end in text:
        text = re.sub(rf"{re.escape(start)}.*?{re.escape(end)}", replacement, text, flags=re.S)
    else:
        text = text.rstrip() + "\n\n" + replacement + "\n"
    path.write_text(text, encoding="utf-8")


def write_profile(vault: Path, profile: dict[str, Any], update_meta: bool = True) -> dict[str, Path]:
    profile_dir = vault / "wiki/profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    rag = vault / "rag"
    rag.mkdir(parents=True, exist_ok=True)
    markdown_path = profile_dir / "postgraduate-profile.md"
    html_path = profile_dir / "postgraduate-profile.html"
    json_path = rag / "postgraduate-profile.json"
    markdown_path.write_text(markdown_report(profile), encoding="utf-8")
    html_path.write_text(html_report(profile), encoding="utf-8")
    json_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if update_meta:
        language = profile["language"]
        link_title = "研究生知识画像" if language == "zh" else "Postgraduate Knowledge Profile"
        section = f"## {link_title}\n- [[profile/postgraduate-profile|{link_title}]]"
        upsert_marker(vault / "wiki/index.md", "POSTGRADUATE-PROFILE", section)
        upsert_marker(vault / "wiki/hot.md", "POSTGRADUATE-PROFILE", section)
        log = vault / "wiki/log.md"
        if log.exists():
            day = profile["generated_at"][:10]
            entry = f"## {day} | profile | {link_title}\n- Generated deterministic knowledge visualization and task-fit advice."
            text = log.read_text(encoding="utf-8", errors="ignore")
            if entry not in text:
                log.write_text(text.rstrip() + "\n\n" + entry + "\n", encoding="utf-8")

    return {"markdown": markdown_path, "html": html_path, "json": json_path}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a deterministic knowledge profile for one Postgraduate vault.")
    parser.add_argument("--root", type=Path, default=Path.home() / "auto-research")
    parser.add_argument("--vault", required=True, help="Vault name or absolute path")
    parser.add_argument("--language", choices=["en", "zh"], default="en")
    parser.add_argument("--no-meta-update", action="store_true", help="Do not update wiki index, hot, or log pages")
    parser.add_argument("--dry-run", action="store_true", help="Print the profile JSON without writing files")
    args = parser.parse_args()

    vault = Path(args.vault)
    if not vault.is_absolute():
        vault = args.root.expanduser().resolve() / vault
    if not vault.is_dir():
        raise SystemExit(f"Vault not found: {vault}")

    profile = build_profile(vault, args.language)
    if args.dry_run:
        print(json.dumps(profile, ensure_ascii=False, indent=2))
        return 0

    paths = write_profile(vault, profile, update_meta=not args.no_meta_update)
    print(f"vault={vault}")
    print(f"best_fit={profile['best_fit']['title']}\tscore={profile['best_fit']['score']:.1f}")
    for key, path in paths.items():
        print(f"{key}={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
