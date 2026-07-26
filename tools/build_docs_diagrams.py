#!/usr/bin/env python3
"""Generate bilingual SVG documentation diagrams for the public repository."""

from __future__ import annotations

import argparse
import html
from pathlib import Path


WIDTH = 1600
HEIGHT = 900
BG = "#F7F8FA"
INK = "#17212B"
MUTED = "#5B6773"
LINE = "#CAD2DA"
WHITE = "#FFFFFF"
TEAL = "#087F73"
BLUE = "#246BCE"
RED = "#D94841"
AMBER = "#C47A00"
GREEN = "#2F855A"
PURPLE = "#7656A8"


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def svg_start(title: str, description: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">',
        f"<title id=\"title\">{esc(title)}</title>",
        f"<desc id=\"desc\">{esc(description)}</desc>",
        "<defs>",
        '<filter id="shadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="5" stdDeviation="7" flood-color="#17212B" flood-opacity="0.10"/></filter>',
        '<marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L10,5 L0,10 z" fill="#7B8794"/></marker>',
        '<style>text{font-family:"Noto Sans CJK SC","Microsoft YaHei",Arial,sans-serif;letter-spacing:0}.title{font-size:38px;font-weight:700;fill:#17212B}.subtitle{font-size:18px;fill:#5B6773}.eyebrow{font-size:14px;font-weight:700;fill:#087F73}.card-title{font-size:21px;font-weight:700;fill:#17212B}.compact{font-size:17px;font-weight:700;fill:#17212B}.body{font-size:16px;fill:#5B6773}.small{font-size:14px;fill:#5B6773}.step{font-size:13px;font-weight:700;fill:#FFFFFF}.white{fill:#FFFFFF}.mono{font-family:"Noto Sans Mono CJK SC","SFMono-Regular",Consolas,monospace}</style>',
        "</defs>",
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{BG}"/>',
    ]


def rect(out: list[str], x: int, y: int, w: int, h: int, fill: str = WHITE, stroke: str = LINE, radius: int = 8, shadow: bool = False, stroke_width: int = 1) -> None:
    filter_attr = ' filter="url(#shadow)"' if shadow else ""
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}"{filter_attr}/>')


def text(out: list[str], x: int, y: int, value: str, cls: str = "body", anchor: str = "start", fill: str | None = None) -> None:
    fill_attr = f' style="fill:{fill}"' if fill else ""
    out.append(f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}"{fill_attr}>{esc(value)}</text>')


def multiline(out: list[str], x: int, y: int, lines: list[str], cls: str = "body", gap: int = 25, anchor: str = "start", fill: str | None = None) -> None:
    fill_attr = f' style="fill:{fill}"' if fill else ""
    out.append(f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}"{fill_attr}>')
    for index, line in enumerate(lines):
        dy = 0 if index == 0 else gap
        out.append(f'<tspan x="{x}" dy="{dy}">{esc(line)}</tspan>')
    out.append("</text>")


def arrow(out: list[str], x1: int, y1: int, x2: int, y2: int, dashed: bool = False, color: str = "#7B8794", width: int = 3) -> None:
    dash = ' stroke-dasharray="8 8"' if dashed else ""
    out.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}" marker-end="url(#arrow)"{dash}/>')


def pill(out: list[str], x: int, y: int, w: int, label: str, fill: str, text_fill: str = WHITE) -> None:
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="30" rx="8" fill="{fill}"/>')
    text(out, x + w // 2, y + 21, label, "small", "middle", text_fill)


def header(out: list[str], eyebrow: str, title_value: str, subtitle_value: str) -> None:
    text(out, 90, 64, eyebrow, "eyebrow")
    text(out, 90, 112, title_value, "title")
    text(out, 90, 148, subtitle_value, "subtitle")
    out.append(f'<line x1="90" y1="176" x2="1510" y2="176" stroke="{LINE}" stroke-width="1"/>')


def workflow(language: str) -> str:
    zh = language == "zh"
    title_value = "把一次调研，变成持续成长的 AI 研究生" if zh else "Turn one research task into a postgraduate that keeps learning"
    subtitle_value = "从想法、全文与证据，到因果知识、RAG 回忆和可审计版本" if zh else "From ideas and full text to causal knowledge, RAG recall, and auditable versions"
    out = svg_start(title_value, subtitle_value)
    header(out, "YOUR AI POSTGRADUATE", title_value, subtitle_value)

    labels_zh = [
        ("IDEA 入库", ["保存原始问题", "建立研究目标"], TEAL),
        ("适配审计", ["复用已有研究生", "或创建新领域"], BLUE),
        ("文献与全文", ["检索 · PDF · OCR", "作者 · DOI · BibTeX"], AMBER),
        ("严格深读", ["问题 · 方法 · 变量", "实验 · 局限 · 反证"], RED),
        ("知识构建", ["论文记忆 · 因果边", "假设 · 可迁移机制"], PURPLE),
        ("RAG 回忆", ["检索验证证据", "跨论文迁移推理"], GREEN),
        ("审计与同步", ["成本 · 质量 · 画像", "Git 可追踪版本"], INK),
    ]
    labels_en = [
        ("Ingest idea", ["Preserve source", "Set research goals"], TEAL),
        ("Audit fit", ["Reuse researcher", "or create domain"], BLUE),
        ("Literature", ["Search · PDF · OCR", "Authors · DOI", "BibTeX"], AMBER),
        ("Read deeply", ["Question", "Method · variables", "Experiments", "Limits · refutation"], RED),
        ("Build knowledge", ["Paper memory", "Causal edges", "Hypotheses", "Mechanisms"], PURPLE),
        ("Recall with RAG", ["Retrieve evidence", "Transfer across papers"], GREEN),
        ("Audit and sync", ["Cost · quality", "Researcher profile", "Git versions"], INK),
    ]
    labels = labels_zh if zh else labels_en
    card_w, card_h, gap = 180, 236, 22
    start_x, y = 90, 240
    for index, (label, body_lines, color) in enumerate(labels):
        x = start_x + index * (card_w + gap)
        rect(out, x, y, card_w, card_h, WHITE, LINE, 8, True)
        out.append(f'<rect x="{x}" y="{y}" width="{card_w}" height="10" rx="5" fill="{color}"/>')
        out.append(f'<circle cx="{x + 34}" cy="{y + 48}" r="19" fill="{color}"/>')
        text(out, x + 34, y + 53, f"{index + 1:02d}", "step", "middle")
        text(out, x + 20, y + 94, label, "card-title" if zh else "compact")
        multiline(out, x + 20, y + 130, body_lines, "body" if zh else "small", 28 if zh else 25)
        if index < len(labels) - 1:
            arrow(out, x + card_w + 4, y + 118, x + card_w + gap - 4, y + 118)

    rail_y = 545
    rect(out, 90, rail_y, 1420, 225, "#111820", "#111820", 8, False)
    text(out, 120, rail_y + 42, "持久产物层" if zh else "Durable artifact layer", "card-title", fill=WHITE)
    text(out, 120, rail_y + 72, "每一步可恢复、可追溯、可审计" if zh else "Every stage is resumable, traceable, and auditable", "body", fill="#B8C4CF")
    artifacts_zh = ["原始 IDEA", "Paper Master", "全文与 BibTeX", "论文卡片", "验证后记忆", "因果知识库", "JSONL RAG", "研究生画像"]
    artifacts_en = ["Raw idea", "Paper master", "Full text + BibTeX", "Paper cards", "Validated memory", "Causal knowledge", "JSONL RAG", "Researcher profile"]
    artifacts = artifacts_zh if zh else artifacts_en
    for index, label in enumerate(artifacts):
        x = 120 + index * 170
        rect(out, x, rail_y + 108, 150, 76, "#202A34", "#43505C", 6)
        text(out, x + 75, rail_y + 153, label, "small", "middle", WHITE)
    pill(out, 1280, 68, 230, "23 Skills · Evidence First", TEAL)
    out.append("</svg>")
    return "\n".join(out)


def evidence(language: str) -> str:
    zh = language == "zh"
    title_value = "证据先行：从论文到可回忆知识" if zh else "Evidence first: from papers to recallable knowledge"
    subtitle_value = "权威文献层不会被图抽取或摘要覆盖；所有推理都能回到原文" if zh else "The authoritative literature layer is never overwritten; reasoning can return to source text"
    out = svg_start(title_value, subtitle_value)
    header(out, "EVIDENCE → MEMORY → RAG", title_value, subtitle_value)

    column_x = [90, 420, 750, 1080]
    widths = [260, 260, 260, 430]
    colors = [BLUE, AMBER, RED, TEAL]
    heads_zh = ["1. 权威文献层", "2. 分块抽取", "3. 证据门禁", "4. 可用知识层"]
    heads_en = ["1. Authoritative layer", "2. Chunk extraction", "3. Evidence gate", "4. Usable knowledge"]
    heads = heads_zh if zh else heads_en
    for x, w, color, head in zip(column_x, widths, colors, heads):
        rect(out, x, 220, w, 520, WHITE, LINE, 8, True)
        out.append(f'<rect x="{x}" y="220" width="{w}" height="8" rx="4" fill="{color}"/>')
        text(out, x + 24, 270, head, "card-title")

    source_zh = [("Paper Master", ["作者、机构、来源、DOI"]), ("PDF / 全文", ["合法取得，原始内容不可变"]), ("BibTeX", ["citation key 与引用元数据"])]
    source_en = [("Paper master", ["Authors, affiliations", "Source and DOI"]), ("PDF / full text", ["Lawfully acquired", "Immutable source"]), ("BibTeX", ["Citation key", "Reference metadata"])]
    for i, (head, body_lines) in enumerate(source_zh if zh else source_en):
        y = 305 + i * 128
        rect(out, 112, y, 216, 96, "#F4F7FB", "#B9C9DD", 6)
        text(out, 132, y + 34, head, "card-title")
        multiline(out, 132, y + 62, body_lines, "small", 21)
    pill(out, 112, 690, 216, "永不被派生产物覆盖" if zh else "Never overwritten", BLUE)

    extraction_zh = [("独立 chunk 保存", ["失败只重跑失败单元"]), ("紧凑论文记忆", ["默认机器回忆层"]), ("Hyper-Extract", ["按需生成细粒度节点与边"])]
    extraction_en = [("Independent chunks", ["Retry only failed units"]), ("Compact paper memory", ["Default machine recall layer"]), ("Hyper-Extract", ["Optional fine-grained", "nodes and edges"])]
    for i, (head, body_lines) in enumerate(extraction_zh if zh else extraction_en):
        y = 305 + i * 128
        rect(out, 442, y, 216, 96, "#FFF9ED", "#E7C987", 6)
        text(out, 462, y + 34, head, "card-title" if zh else "compact")
        multiline(out, 462, y + 62, body_lines, "small", 21)
    pill(out, 442, 690, 216, "Medium 默认 · Strong 升级" if zh else "Medium · Strong on failure", AMBER)

    gate_zh = [("引文匹配", ["exact / layout-recovered"]), ("Claim-support", ["结论是否真被原文支撑"]), ("因果边界", ["相关 ≠ 已识别因果效应"])]
    gate_en = [("Quotation match", ["exact / layout-recovered"]), ("Claim support", ["Does the source", "support the claim?"]), ("Causal boundary", ["Association ≠", "identified effect"])]
    for i, (head, body_lines) in enumerate(gate_zh if zh else gate_en):
        y = 305 + i * 128
        rect(out, 772, y, 216, 96, "#FFF3F2", "#EAB0AC", 6)
        text(out, 792, y + 34, head, "card-title")
        multiline(out, 792, y + 62, body_lines, "small", 21)
    pill(out, 772, 690, 216, "不通过则拒绝或降级" if zh else "Reject or downgrade failures", RED)

    outputs_zh = [("因果知识库", ["变量 · 机制 · 干预 · 边", "每条关系携带证据状态"]), ("Provider-neutral RAG", ["JSONL 语料 · 原文定位", "检索后回填证据再推理"]), ("研究生画像", ["知识准备度 · 任务适配", "缺口与下一步建议"])]
    outputs_en = [("Causal knowledge base", ["Variables · mechanisms · interventions", "Evidence state on every relation"]), ("Provider-neutral RAG", ["JSONL corpus · source locations", "Rehydrate evidence before reasoning"]), ("Researcher profile", ["Readiness · task fit", "Gaps and next actions"])]
    for i, (head, lines) in enumerate(outputs_zh if zh else outputs_en):
        y = 305 + i * 128
        rect(out, 1104, y, 382, 96, "#F1FAF8", "#9CCFC8", 6)
        text(out, 1126, y + 32, head, "card-title")
        multiline(out, 1126, y + 59, lines, "small", 22)
    pill(out, 1104, 690, 382, "每个答案都能回到论文证据" if zh else "Every answer can return to paper evidence", TEAL)

    arrow(out, 354, 475, 410, 475)
    arrow(out, 684, 475, 740, 475)
    arrow(out, 1014, 475, 1070, 475)
    text(out, 800, 820, "Evidence is a gate, not a decoration." if not zh else "证据是门禁，不是装饰。", "card-title", "middle")
    out.append("</svg>")
    return "\n".join(out)


def routing(language: str) -> str:
    zh = language == "zh"
    title_value = "先选择合适的研究生，再开始调研" if zh else "Assign the right postgraduate before research begins"
    subtitle_value = "严格两级：宽领域研究生 → 平级研究线；共享能力，隔离证据归属" if zh else "Exactly two levels: broad postgraduate → peer research lines; shared capability, isolated evidence ownership"
    out = svg_start(title_value, subtitle_value)
    header(out, "RESEARCHER ASSIGNMENT GATE", title_value, subtitle_value)

    rect(out, 90, 235, 250, 150, WHITE, LINE, 8, True)
    pill(out, 112, 255, 112, "NEW TASK" if not zh else "新调研任务", INK)
    if zh:
        text(out, 112, 319, "研究问题 + 目标 + 约束", "card-title")
        text(out, 112, 351, "先不检索论文", "body")
    else:
        multiline(out, 112, 313, ["Question + goal", "+ constraints"], "compact", 25)
        text(out, 112, 365, "No literature work yet", "body")

    rect(out, 440, 220, 360, 250, "#F4F7FB", "#AFC3DB", 8, True)
    text(out, 466, 265, "适配审计" if zh else "Fit audit", "card-title")
    audit_zh = ["领域归属是否一致？", "已有知识能否直接迁移？", "画像 / 索引 / hot / RAG 是否命中？", "仅方法相似不算适配"]
    audit_en = ["Does domain ownership match?", "Is stored knowledge directly transferable?", "Do profile / index / hot / RAG match?", "Generic method overlap is insufficient"]
    for i, line in enumerate(audit_zh if zh else audit_en):
        y = 310 + i * 37
        out.append(f'<circle cx="470" cy="{y - 5}" r="5" fill="{BLUE}"/>')
        text(out, 486, y, line, "body")
    arrow(out, 344, 310, 428, 310)

    rect(out, 900, 220, 610, 540, WHITE, LINE, 8, True)
    text(out, 930, 265, "持久化分配结果" if zh else "Persist the assignment", "card-title")
    text(out, 930, 298, "wiki/meta/<idea-id>-postgraduate-assignment.md", "small mono")

    rect(out, 950, 338, 510, 92, "#EAF7F5", "#91C8C1", 6)
    text(out, 1205, 375, "Postgraduate_<BroadDomain>" if not zh else "Postgraduate_<宽领域>", "card-title", "middle")
    text(out, 1205, 404, "一级：领域研究生，共享领域知识与 RAG" if zh else "Level 1: domain researcher with shared knowledge and RAG", "small", "middle")

    line_y = 500
    line_labels_zh = [("研究线 A", "独立 paper master / claims"), ("研究线 B", "独立 hypotheses / experiments"), ("新研究线", "独立 evidence ownership")]
    line_labels_en = [("Research line A", "Own paper master / claims"), ("Research line B", "Own hypotheses / experiments"), ("New research line", "Own evidence provenance")]
    for i, (head, body) in enumerate(line_labels_zh if zh else line_labels_en):
        x = 935 + i * 180
        rect(out, x, line_y, 160, 118, "#FFF9ED" if i < 2 else "#F3F1F8", "#D7C28D" if i < 2 else "#BFAED5", 6)
        if not zh and i == 2:
            multiline(out, x + 80, line_y + 34, ["New research", "line"], "compact", 21, "middle")
            body_y = line_y + 86
        else:
            text(out, x + 80, line_y + 42, head, "card-title" if zh else "compact", "middle")
            body_y = line_y + 72
        multiline(out, x + 80, body_y, body.split(" / ") if " / " in body else [body], "small", 20, "middle")
        out.append(f'<line x1="1205" y1="430" x2="{x + 80}" y2="{line_y}" stroke="#7B8794" stroke-width="2"/>')

    out.append(f'<line x1="930" y1="665" x2="1480" y2="665" stroke="{RED}" stroke-width="3" stroke-dasharray="10 8"/>')
    text(out, 1205, 700, "禁止第三级：研究线下面不再嵌套项目" if zh else "No third level: research lines cannot contain nested projects", "card-title" if zh else "compact", "middle", RED)

    arrow(out, 804, 310, 888, 310)
    pill(out, 454, 510, 155, "复用" if zh else "REUSE", TEAL)
    if zh:
        text(out, 454, 566, "领域 + 直接证据均匹配", "body")
    else:
        multiline(out, 454, 566, ["Domain + direct", "evidence match"], "small", 22)
    pill(out, 630, 510, 155, "新建" if zh else "CREATE", AMBER)
    if zh:
        text(out, 630, 566, "无现有研究生适配", "body")
    else:
        multiline(out, 630, 566, ["No current", "researcher fits"], "small", 22)
    multiline(out, 90, 530, ["决策原则" if zh else "Decision rule", "共享领域知识", "隔离研究证据", "保留完整溯源"] if zh else ["Share domain knowledge", "Isolate project evidence", "Preserve provenance"], "card-title" if zh else "body", 35)
    out.append("</svg>")
    return "\n".join(out)


DIAGRAMS = {
    "system-workflow": workflow,
    "evidence-to-rag": evidence,
    "researcher-routing": routing,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("docs/assets"))
    parser.add_argument("--png", action="store_true", help="Also render PNG previews with CairoSVG.")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for name, builder in DIAGRAMS.items():
        for language in ("zh", "en"):
            target = args.output / f"{name}-{language}.svg"
            target.write_text(builder(language) + "\n", encoding="utf-8")
            print(target)
            if args.png:
                try:
                    import cairosvg
                except ImportError as exc:
                    raise SystemExit("CairoSVG is required for --png: python -m pip install cairosvg") from exc
                png_target = target.with_suffix(".png")
                cairosvg.svg2png(url=str(target), write_to=str(png_target), output_width=1600, output_height=900)
                print(png_target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
