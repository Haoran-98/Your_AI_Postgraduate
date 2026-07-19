#!/usr/bin/env python3
"""Build compact, source-grounded paper memories for long-term RAG."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import yaml
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from hyperextract_clients import UsageRecorder, create_llm_client, provider_configured
from validate_hyperextract_evidence import load_corpus, location_chunks, quote_matches


MemoryKind = Literal[
    "research_question",
    "contribution",
    "variable",
    "dataset",
    "study_design",
    "experiment",
    "finding",
    "limitation",
    "mechanism",
    "causal_claim",
    "contradiction",
    "transferable_principle",
    "open_question",
]
CausalStatus = Literal[
    "none",
    "reported_association",
    "author_causal_claim",
    "identified_causal_effect",
    "mechanistic_hypothesis",
]
RelationType = Literal[
    "",
    "causes",
    "mediates",
    "moderates",
    "supports",
    "refutes",
    "complicates",
    "mitigates",
    "limits",
    "measures",
    "uses",
    "evaluates",
    "limited_by",
]


class MemoryItem(BaseModel):
    kind: MemoryKind
    statement: str
    importance: int = Field(default=3, ge=1, le=5)
    evidence_quote: str
    location: str
    boundary: str = ""
    causal_status: CausalStatus = "none"
    role: str = ""
    entities: list[str] = Field(default_factory=list)
    subject: str = ""
    relation: RelationType = ""
    object: str = ""


class PaperMemory(BaseModel):
    one_sentence_summary: str
    study_design: str
    population: str = ""
    intervention: str = ""
    comparator: str = ""
    outcomes: list[str] = Field(default_factory=list)
    affiliations: list[str] = Field(default_factory=list)
    memories: list[MemoryItem] = Field(default_factory=list)


class PaperConsolidation(BaseModel):
    one_sentence_summary: str
    study_design: str
    population: str = ""
    intervention: str = ""
    comparator: str = ""
    outcomes: list[str] = Field(default_factory=list)
    affiliations: list[str] = Field(default_factory=list)
    selected_memory_ids: list[str] = Field(default_factory=list)


class MemoryReview(BaseModel):
    memory_id: str
    verdict: Literal["accept", "narrow", "reject"]
    revised_statement: str = ""
    reason: str = ""
    causal_status: CausalStatus = "none"
    subject: str = ""
    relation: RelationType = ""
    object: str = ""


class MemoryReviewBatch(BaseModel):
    reviews: list[MemoryReview] = Field(default_factory=list)


EXTRACTION_PROMPT = """You create durable scientific memory, not an exhaustive graph.
Read the supplied paper text and retain only knowledge a careful researcher should remember and transfer to future research questions.

Return at most {max_memories} memories total. Prioritize the paper's own research questions, contributions, design, variables, datasets, experiments, numeric findings, limitations, mechanisms, causal claims, contradictions, transferable principles, and open questions. Exclude ordinary background facts and cited-work summaries unless they define this paper's method or comparison.

Every memory must:
- state one concise fact in at most 40 words;
- use one short contiguous evidence_quote copied character-for-character from exactly one TEXT block;
- copy the matching LOCATION line exactly;
- preserve important numbers, sample sizes, effect sizes, reliability values, and boundary conditions;
- assign causal_status conservatively; identified_causal_effect requires a design that identifies an intervention effect;
- fill subject/relation/object only when a useful directed relation is supported;
- list no more than four stable entities.

Do not create support/refutation for a particular external idea. Store domain-general evidence that can be reused later. Study profile fields are compact paper-level summaries. Affiliations must come only from the title page. If evidence is absent, omit the memory rather than inventing it."""

CONSOLIDATION_PROMPT = """Select durable memories from all parts of one paper and produce a compact paper profile.
Return at most {max_memories} candidate IDs in selected_memory_ids. Keep the most central, evidence-strong, transferable, causal, contradictory, and numerically important candidates. Preserve coverage of research questions, study design, datasets, primary results, critical limitations, mechanisms, and boundary conditions when present.

Candidate evidence is immutable. Return IDs only; do not copy or rewrite statements, quotes, locations, or relations. Remove duplicates and background-only candidates. Do not introduce external knowledge."""

REVIEW_PROMPT = """Audit each candidate long-term memory against its quoted evidence and source chunk.

Use accept only when the full statement is supported. Use narrow when a shorter corrected statement is supported, and provide revised_statement. Use reject when the evidence does not support the claim. A verbatim quote match alone is insufficient: numbers, comparisons, causal wording, scope, and all clauses must be supported.

For mechanism, causal_claim, contradiction, or transferable_principle items, provide subject/relation/object only when a useful directed relation is explicit or directly supported. Keep causal_status conservative. Do not introduce outside knowledge. Return one review for every memory_id."""


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_records(corpus: Path, paper_id: str) -> list[dict[str, object]]:
    records = []
    with corpus.open(encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            metadata = item.get("metadata", {})
            if (
                metadata.get("paper_id") == paper_id
                and metadata.get("source_type") == "paper-fulltext"
                and metadata.get("rag_evidence_level") != "blocked"
            ):
                records.append(item)
    return records


def readable_paper_chars(corpus: Path) -> dict[str, int]:
    totals: Counter[str] = Counter()
    with corpus.open(encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            metadata = item.get("metadata", {})
            if (
                metadata.get("source_type") == "paper-fulltext"
                and metadata.get("rag_evidence_level") != "blocked"
            ):
                totals[str(metadata.get("paper_id"))] += len(str(item.get("text", "")))
    return dict(totals)


def location(record: dict[str, object]) -> str:
    metadata = record["metadata"]
    page = metadata.get("page") if metadata.get("page") is not None else "unknown"
    section = metadata.get("section") or "unknown"
    return f"{metadata.get('paper_id')}|page={page}|section={section}|chunk={record['id']}"


def render_records(records: list[dict[str, object]]) -> str:
    lines = []
    for record in records:
        metadata = record["metadata"]
        lines.extend(
            [
                "[SOURCE_CHUNK]",
                f"LOCATION: {location(record)}",
                f"TITLE: {metadata.get('title') or 'unknown'}",
                "[TEXT]",
                str(record["text"]),
                "[/TEXT]",
                "[/SOURCE_CHUNK]",
                "",
            ]
        )
    return "\n".join(lines)


def partition_records(records: list[dict[str, object]], max_chars: int) -> list[list[dict[str, object]]]:
    parts: list[list[dict[str, object]]] = []
    current: list[dict[str, object]] = []
    current_chars = 0
    for record in records:
        size = len(str(record["text"]))
        if current and current_chars + size > max_chars:
            parts.append(current)
            current = []
            current_chars = 0
        current.append(record)
        current_chars += size
    if current:
        parts.append(current)
    return parts


def frontmatter(path: Path) -> tuple[dict[str, object], str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    return yaml.safe_load(text[4:end]) or {}, text[end + 5 :]


def bullet(body: str, label: str) -> str:
    match = re.search(rf"^- {re.escape(label)}:\s*(.+)$", body, re.M)
    return match.group(1).strip() if match else ""


def bibtex_authors(bibtex: str) -> list[str]:
    fields = re.findall(r"\bauthor\s*=\s*\{([^}]*)\}", bibtex, re.I | re.S)
    fields.extend(re.findall(r'\bauthor\s*=\s*"([^"]*)"', bibtex, re.I | re.S))
    return [
        name.strip()
        for field in fields
        for name in re.split(r"\s+and\s+", re.sub(r"\s+", " ", field).strip())
        if name.strip()
    ]


def bibliography(vault: Path, paper_id: str, title: str) -> dict[str, object]:
    matches = sorted((vault / "wiki/papers").glob(f"{paper_id}-*.md"))
    if not matches:
        return {"paper_id": paper_id, "title": title}
    card = matches[0]
    metadata, body = frontmatter(card)
    heading = re.search(r"^#\s+(.+)$", body, re.M)
    bibtex = str(metadata.get("bibtex") or "").strip()
    citation = re.search(r"@\w+\{\s*([^,]+)", bibtex)
    doi = re.search(r"\bdoi\s*=\s*[\{\"]([^\}\"]+)", bibtex, re.I)
    year_source = bullet(body, "Year/source")
    year_match = re.search(r"\b(?:19|20)\d{2}\b", year_source)
    card_authors = bullet(body, "Authors") or bullet(body, "Author")
    authors = bibtex_authors(bibtex) or [
        value.strip().rstrip(".")
        for value in re.split(r"\s*(?:,|\band\b)\s*", card_authors)
        if value.strip()
    ]
    return {
        "paper_id": paper_id,
        "title": heading.group(1).strip() if heading else title,
        "authors": authors,
        "year_source": year_source,
        "year": year_match.group(0) if year_match else "",
        "url": bullet(body, "URL"),
        "doi": doi.group(1) if doi else "",
        "citation_key": citation.group(1).strip() if citation else "",
        "bibtex": bibtex,
        "paper_card": str(card.relative_to(vault)),
    }


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def extract_memory(llm, prompt: str, source: str) -> PaperMemory:
    structured = llm.with_structured_output(PaperMemory, method="function_calling")
    return structured.invoke([SystemMessage(content=prompt), HumanMessage(content=source)])


def consolidate_memory(
    llm,
    part_outputs: list[PaperMemory],
    maximum: int,
    corpus: dict[str, dict[str, object]],
) -> PaperMemory:
    candidates = []
    candidate_map = {}
    for part_index, part in enumerate(part_outputs, start=1):
        for memory_index, item in enumerate(part.memories, start=1):
            candidate_id = f"part-{part_index:03d}-memory-{memory_index:03d}"
            if quote_matches(item.evidence_quote, [item.location], corpus):
                match_type = "exact"
            elif layout_quote_matches(item.evidence_quote, [item.location], corpus):
                match_type = "layout-recovered"
            else:
                continue
            candidate_map[candidate_id] = item
            candidates.append({"candidate_id": candidate_id, "evidence_match": match_type, **item.model_dump()})
    structured = llm.with_structured_output(PaperConsolidation, method="function_calling")
    result = structured.invoke(
        [
            SystemMessage(content=CONSOLIDATION_PROMPT.format(max_memories=maximum)),
            HumanMessage(content=json.dumps(candidates, ensure_ascii=False)),
        ]
    )
    selected = []
    seen = set()
    core_kinds = (
        "research_question",
        "contribution",
        "study_design",
        "experiment",
        "dataset",
        "variable",
        "finding",
        "limitation",
        "mechanism",
        "contradiction",
        "transferable_principle",
        "open_question",
    )
    for kind in core_kinds:
        matches = [
            (candidate_id, item)
            for candidate_id, item in candidate_map.items()
            if item.kind == kind
        ]
        if matches:
            candidate_id, item = max(matches, key=lambda value: value[1].importance)
            selected.append(item)
            seen.add(candidate_id)
    for candidate_id in result.selected_memory_ids:
        if candidate_id in candidate_map and candidate_id not in seen:
            selected.append(candidate_map[candidate_id])
            seen.add(candidate_id)
        if len(selected) >= maximum:
            break
    if not selected:
        selected = deduplicate(list(candidate_map.values()), maximum)
    affiliations = list(dict.fromkeys(result.affiliations + [value for part in part_outputs for value in part.affiliations]))
    return PaperMemory(
        one_sentence_summary=result.one_sentence_summary,
        study_design=result.study_design,
        population=result.population,
        intervention=result.intervention,
        comparator=result.comparator,
        outcomes=result.outcomes,
        affiliations=affiliations,
        memories=selected,
    )


def deduplicate(memories: list[MemoryItem], maximum: int) -> list[MemoryItem]:
    seen = set()
    unique = []
    for item in memories:
        key = re.sub(r"\s+", " ", item.statement).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    indexed = list(enumerate(unique))
    indexed.sort(key=lambda pair: (-pair[1].importance, pair[0]))
    return [item for _, item in indexed[:maximum]]


def evidence_tokens(text: str) -> list[str]:
    dehyphenated = re.sub(r"(?<=\w)-\s+(?=\w)", "", text)
    return re.findall(r"[a-z0-9]+", dehyphenated.lower())


def next_layout_token(source: list[str], expected: str, position: int, limit: int) -> int:
    for index in range(position + 1, limit):
        if source[index] == expected:
            return index
        if len(expected) >= 4 and source[index].endswith(expected):
            return index
        prefix = 0
        while prefix < min(len(source[index]), len(expected)) and source[index][prefix] == expected[prefix]:
            prefix += 1
        if prefix < 3 or len(expected) - prefix < 2:
            continue
        suffix = expected[prefix:]
        for suffix_index in range(index + 1, limit):
            if source[suffix_index] == suffix:
                return suffix_index
    return -1


def layout_quote_matches(quote: str, locations: list[str], corpus: dict[str, dict[str, object]]) -> bool:
    expected = evidence_tokens(quote)
    if len(expected) < 8:
        return False
    for location_value in locations:
        for chunk_id in location_chunks(location_value):
            item = corpus.get(chunk_id)
            if not item:
                continue
            source = evidence_tokens(str(item.get("text", "")))
            for start in (index for index, token in enumerate(source) if token == expected[0]):
                position = start
                matched = True
                for token in expected[1:]:
                    limit = min(len(source), position + 121)
                    position = next_layout_token(source, token, position, limit)
                    if position < 0:
                        matched = False
                        break
                if matched and position - start <= len(expected) * 8:
                    return True
    return False


def validate_memory(
    memory: PaperMemory,
    paper_id: str,
    corpus: dict[str, dict[str, object]],
    maximum: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    valid = []
    rejected = []
    for index, item in enumerate(deduplicate(memory.memories, maximum), start=1):
        value = item.model_dump()
        value["memory_id"] = f"{paper_id}-M{index:03d}"
        value["source_chunk_ids"] = location_chunks(item.location)
        if quote_matches(item.evidence_quote, [item.location], corpus):
            value["evidence_match"] = "exact"
            value["review_status"] = "machine-validated"
            valid.append(value)
        elif layout_quote_matches(item.evidence_quote, [item.location], corpus):
            value["evidence_match"] = "layout-recovered"
            value["review_status"] = "layout-recovered"
            valid.append(value)
        else:
            value["evidence_match"] = "unmatched"
            value["review_status"] = "quote-unmatched"
            rejected.append(value)
    return valid, rejected


def review_memories(
    llm,
    recorder: UsageRecorder,
    paper_id: str,
    memories: list[dict[str, object]],
    corpus: dict[str, dict[str, object]],
    model_strength: str,
    attempt: int = 1,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    chunk_ids = sorted({chunk for item in memories for chunk in item.get("source_chunk_ids", [])})
    source = {
        "memories": memories,
        "source_chunks": {
            chunk_id: str(corpus.get(chunk_id, {}).get("text", ""))
            for chunk_id in chunk_ids
        },
    }
    recorder.set_context(
        unit_id=f"{paper_id}:paper-memory:review",
        paper_id=paper_id,
        mode="paper-memory-review",
        model_strength=model_strength,
        attempt=attempt,
    )
    structured = llm.with_structured_output(MemoryReviewBatch, method="function_calling")
    result = structured.invoke(
        [
            SystemMessage(content=REVIEW_PROMPT),
            HumanMessage(content=json.dumps(source, ensure_ascii=False)),
        ]
    )
    reviews = {item.memory_id: item for item in result.reviews}
    accepted = []
    rejected = []
    for memory in memories:
        review = reviews.get(str(memory["memory_id"]))
        if review is None:
            value = dict(memory)
            value["review_status"] = "machine-validated-unreviewed"
            accepted.append(value)
            continue
        value = dict(memory)
        value["review_reason"] = review.reason
        if review.verdict == "reject":
            value["review_status"] = "llm-review-rejected"
            rejected.append(value)
            continue
        if review.verdict == "narrow" and review.revised_statement.strip():
            value["statement"] = review.revised_statement.strip()
        if review.subject and review.relation and review.object:
            value["subject"] = review.subject
            value["relation"] = review.relation
            value["object"] = review.object
            value["causal_status"] = review.causal_status
        value["review_status"] = "machine-reviewed"
        accepted.append(value)
    return accepted, rejected


def usage_for_paper(path: Path, paper_id: str) -> dict[str, object]:
    totals: Counter[str] = Counter()
    by_mode: dict[str, Counter[str]] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row.get("paper_id") != paper_id:
                continue
            mode = str(row.get("mode") or "unknown")
            bucket = by_mode.setdefault(mode, Counter())
            totals["requests"] += 1
            bucket["requests"] += 1
            totals["elapsed_s"] += float(row.get("elapsed_s") or 0)
            bucket["elapsed_s"] += float(row.get("elapsed_s") or 0)
            if row.get("status") == "error":
                totals["errors"] += 1
                bucket["errors"] += 1
            for key in ("input_tokens", "output_tokens", "total_tokens", "input_chars", "output_chars"):
                value = int(row.get(key) or 0)
                totals[key] += value
                bucket[key] += value
    return {**dict(totals), "by_mode": {key: dict(value) for key, value in by_mode.items()}}


def write_cost_audit(base: Path, vault: Path, wrapper: dict[str, object]) -> None:
    totals = readable_paper_chars(vault / "rag/corpus.jsonl")
    source_chars = int(wrapper["source_chars"])
    factor = sum(totals.values()) / source_chars if source_chars else 0
    usage = wrapper["usage"]
    atomic_json(
        base / "audits" / f"{wrapper['paper_id']}.json",
        {
            "actual": {
                **usage,
                "source_records": wrapper["source_records"],
                "source_chars": source_chars,
                "parts": wrapper["parts"],
                "validated_memories": len(wrapper["validated_memories"]),
                "rejected_memories": len(wrapper["rejected_memories"]),
                "bibliography_preserved": bool(wrapper["bibliography"].get("bibtex")),
            },
            "simple_character_projection": {
                "eligible_papers": len(totals),
                "eligible_source_chars": sum(totals.values()),
                "scale_factor": round(factor, 4),
                "requests": round(int(usage.get("requests", 0)) * factor),
                "input_tokens": round(int(usage.get("input_tokens", 0)) * factor),
                "output_tokens": round(int(usage.get("output_tokens", 0)) * factor),
                "total_tokens": round(int(usage.get("total_tokens", 0)) * factor),
                "note": "Long papers use multiple part extractions plus consolidation, so this is a preliminary lower-confidence projection.",
            },
        },
    )


def rebuild_outputs(base: Path, vault: Path) -> None:
    corpus_path = base / "corpus.jsonl"
    edge_path = base / "causal-edges.jsonl"
    manifest = {"papers": 0, "memories": 0, "causal_edges": 0, "bibliographies": 0}
    with corpus_path.open("w", encoding="utf-8") as corpus_out, edge_path.open("w", encoding="utf-8") as edge_out:
        for path in sorted((base / "papers").glob("P*.json")):
            wrapper = json.loads(path.read_text(encoding="utf-8"))
            bibliography_data = wrapper["bibliography"]
            profile = wrapper["paper_memory"]
            paper_id = bibliography_data["paper_id"]
            bibliography_id = f"{vault.name}:{paper_id}:bibliography"
            bibliography_record = {
                "schema_version": "paper-memory-1.0",
                "id": bibliography_id,
                "text": "\n".join(
                    value
                    for value in (
                        bibliography_data.get("title", ""),
                        ", ".join(bibliography_data.get("authors", [])),
                        bibliography_data.get("year_source", ""),
                        bibliography_data.get("url", ""),
                        bibliography_data.get("doi", ""),
                        ", ".join(profile.get("affiliations", [])),
                        bibliography_data.get("bibtex", ""),
                    )
                    if value
                ),
                "metadata": {
                    "vault": vault.name,
                    "paper_id": paper_id,
                    "source_type": "paper-bibliography",
                    "rag_evidence_level": "bibliographic",
                    "review_status": "metadata-preserved",
                    **bibliography_data,
                },
            }
            corpus_out.write(json.dumps(bibliography_record, ensure_ascii=False) + "\n")
            profile_record = {
                "schema_version": "paper-memory-1.0",
                "id": f"{vault.name}:{paper_id}:profile",
                "text": "\n".join(
                    [
                        bibliography_data.get("title", ""),
                        profile.get("one_sentence_summary", ""),
                        f"Study design: {profile.get('study_design', '')}",
                        f"Population: {profile.get('population', '')}",
                        f"Intervention: {profile.get('intervention', '')}",
                        f"Comparator: {profile.get('comparator', '')}",
                        f"Outcomes: {', '.join(profile.get('outcomes', []))}",
                    ]
                ),
                "metadata": {
                    "vault": vault.name,
                    "paper_id": paper_id,
                    "source_type": "paper-profile",
                    "rag_evidence_level": "machine-synthesis",
                    "review_status": "unreviewed",
                    "bibliography_ref": bibliography_id,
                    "paper_card": bibliography_data.get("paper_card", ""),
                    "affiliations": profile.get("affiliations", []),
                },
            }
            corpus_out.write(json.dumps(profile_record, ensure_ascii=False) + "\n")
            for item in wrapper["validated_memories"]:
                record_id = f"{vault.name}:{paper_id}:memory:{item['memory_id']}"
                record = {
                    "schema_version": "paper-memory-1.0",
                    "id": record_id,
                    "text": "\n".join(
                        value
                        for value in (
                            bibliography_data.get("title", ""),
                            f"{item['kind']}: {item['statement']}",
                            f"Boundary: {item.get('boundary', '')}" if item.get("boundary") else "",
                            f"Evidence: {item['evidence_quote']}",
                        )
                        if value
                    ),
                    "metadata": {
                        "vault": vault.name,
                        "paper_id": paper_id,
                        "source_type": "paper-memory",
                        "memory_id": item["memory_id"],
                        "memory_kind": item["kind"],
                        "importance": item["importance"],
                        "causal_status": item["causal_status"],
                        "source_chunk_ids": item["source_chunk_ids"],
                        "location": item["location"],
                        "rag_evidence_level": item.get("evidence_match", "exact"),
                        "review_status": item.get("review_status", "machine-validated"),
                        "bibliography_ref": bibliography_id,
                        "citation_key": bibliography_data.get("citation_key", ""),
                        "url": bibliography_data.get("url", ""),
                        "doi": bibliography_data.get("doi", ""),
                    },
                }
                corpus_out.write(json.dumps(record, ensure_ascii=False) + "\n")
                if item.get("subject") and item.get("relation") and item.get("object"):
                    edge = {
                        "id": digest(f"{paper_id}|{item['subject']}|{item['relation']}|{item['object']}"),
                        "paper_id": paper_id,
                        "source": item["subject"],
                        "relation": item["relation"],
                        "target": item["object"],
                        "memory_id": item["memory_id"],
                        "causal_status": item["causal_status"],
                    }
                    edge_out.write(json.dumps(edge, ensure_ascii=False) + "\n")
                    manifest["causal_edges"] += 1
            manifest["papers"] += 1
            manifest["bibliographies"] += 1
            manifest["memories"] += len(wrapper["validated_memories"])
    manifest.update(
        {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "schema_version": "paper-memory-1.0",
            "raw_corpus": "../corpus.jsonl",
            "memory_corpus": "corpus.jsonl",
            "causal_edges_file": "causal-edges.jsonl",
            "retrieval_policy": "memory first, causal expansion second, raw source chunks last",
        }
    )
    atomic_json(base / "manifest.json", manifest)


def write_markdown(vault: Path, wrapper: dict[str, object]) -> None:
    bibliography_data = wrapper["bibliography"]
    memory = wrapper["paper_memory"]
    output = vault / "wiki/evidence/paper-memory" / f"{bibliography_data['paper_id']}-paper-memory.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        "type: paper-memory",
        f"domain: {vault.name.replace('Postgraduate_', '')}",
        "status: machine-validated",
        f"updated: {datetime.now().date().isoformat()}",
        f"paper_id: {bibliography_data['paper_id']}",
        f"citation_key: {bibliography_data.get('citation_key', '')}",
        "---",
        "",
        f"# {bibliography_data.get('title', bibliography_data['paper_id'])} - Paper Memory",
        "",
        "## Bibliography",
        f"- Authors: {', '.join(bibliography_data.get('authors', []))}",
        f"- Year/source: {bibliography_data.get('year_source', '')}",
        f"- URL: {bibliography_data.get('url', '')}",
        f"- DOI: {bibliography_data.get('doi', '')}",
        f"- Paper card: [[{Path(bibliography_data.get('paper_card', '')).stem}]]",
        "",
        "```bibtex",
        bibliography_data.get("bibtex", ""),
        "```",
        "",
        "## Study Profile",
        memory.get("one_sentence_summary", ""),
        "",
        f"- Design: {memory.get('study_design', '')}",
        f"- Population: {memory.get('population', '')}",
        f"- Intervention: {memory.get('intervention', '')}",
        f"- Comparator: {memory.get('comparator', '')}",
        f"- Outcomes: {', '.join(memory.get('outcomes', []))}",
        f"- Affiliations: {', '.join(memory.get('affiliations', []))}",
        "",
        "## Validated Memories",
    ]
    grouped: dict[str, list[dict[str, object]]] = {}
    for item in wrapper["validated_memories"]:
        grouped.setdefault(item["kind"], []).append(item)
    for kind, items in grouped.items():
        lines.extend(["", f"### {kind.replace('_', ' ').title()}"])
        for item in items:
            lines.append(
                f"- **{item['memory_id']} / importance {item['importance']}**: {item['statement']} "
                f"Evidence: \"{item['evidence_quote']}\" ({item['location']}; {item.get('evidence_match', 'exact')})"
            )
    lines.extend(["", "## Validation", f"- Retained: {len(wrapper['validated_memories'])}", f"- Quote-unmatched: {len(wrapper['rejected_memories'])}"])
    output.write_text("\n".join(line.rstrip() for line in lines) + "\n", encoding="utf-8")


def run_paper(vault: Path, paper_id: str, args, recorder: UsageRecorder) -> str:
    corpus_path = vault / "rag/corpus.jsonl"
    records = load_records(corpus_path, paper_id)
    if not records:
        return "blocked"
    base = vault / "rag/paper-memory"
    output = base / "papers" / f"{paper_id}.json"
    failure = base / "failures" / f"{paper_id}.json"
    if output.exists() and not args.force and not args.rebuild_from_parts:
        return "skipped"
    if failure.exists() and not args.retry_failures and not args.force:
        return "skipped-failure"
    if args.force:
        output.unlink(missing_ok=True)
        failure.unlink(missing_ok=True)
    previous_attempt = json.loads(failure.read_text()).get("attempt", 0) if failure.exists() else 0
    attempt = int(previous_attempt) + 1
    parts = partition_records(records, args.part_chars)
    corpus = load_corpus(corpus_path)
    llm = create_llm_client(recorder, strength=args.model_strength, timeout=args.timeout)
    part_outputs = []
    started = time.monotonic()
    current_unit = f"{paper_id}:paper-memory"
    try:
        for index, part in enumerate(parts, start=1):
            current_unit = f"{paper_id}:paper-memory:part-{index:03d}"
            part_path = base / "parts" / paper_id / f"part-{index:03d}.json"
            if part_path.exists() and not args.force:
                part_outputs.append(PaperMemory.model_validate(json.loads(part_path.read_text())["paper_memory"]))
                continue
            recorder.set_context(
                unit_id=current_unit,
                paper_id=paper_id,
                mode="paper-memory-extract",
                model_strength=args.model_strength,
                attempt=attempt,
            )
            prompt = EXTRACTION_PROMPT.format(max_memories=args.max_memories if len(parts) == 1 else args.part_memories)
            memory = extract_memory(llm, prompt, render_records(part))
            atomic_json(
                part_path,
                {
                    "paper_id": paper_id,
                    "part": index,
                    "parts_total": len(parts),
                    "source_chunk_ids": [item["id"] for item in part],
                    "paper_memory": memory.model_dump(),
                },
            )
            part_outputs.append(memory)
        if len(part_outputs) == 1:
            memory = part_outputs[0]
        else:
            current_unit = f"{paper_id}:paper-memory:consolidation"
            recorder.set_context(
                unit_id=current_unit,
                paper_id=paper_id,
                mode="paper-memory-consolidate",
                model_strength=args.model_strength,
                attempt=attempt,
            )
            memory = consolidate_memory(llm, part_outputs, args.max_memories, corpus)
    except Exception as exc:
        atomic_json(
            failure,
            {
                "paper_id": paper_id,
                "unit_id": current_unit,
                "attempt": attempt,
                "status": "failed",
                "elapsed_s": round(time.monotonic() - started, 3),
                "error_type": type(exc).__name__,
                "error": str(exc)[:2000],
            },
        )
        return "failed"
    valid, rejected = validate_memory(memory, paper_id, corpus, args.max_memories)
    if valid and not args.skip_review:
        valid, review_rejected = review_memories(
            llm,
            recorder,
            paper_id,
            valid,
            corpus,
            args.model_strength,
            attempt,
        )
        rejected.extend(review_rejected)
    title = str(records[0]["metadata"].get("title") or paper_id)
    bibliography_data = bibliography(vault, paper_id, title)
    bibliography_data["affiliations"] = memory.affiliations
    wrapper = {
        "schema_version": "paper-memory-1.0",
        "paper_id": paper_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_records": len(records),
        "source_chars": sum(len(str(item["text"])) for item in records),
        "parts": len(parts),
        "bibliography": bibliography_data,
        "paper_memory": {key: value for key, value in memory.model_dump().items() if key != "memories"},
        "validated_memories": valid,
        "rejected_memories": rejected,
        "usage": usage_for_paper(base / "usage.jsonl", paper_id),
        "elapsed_s": round(time.monotonic() - started, 3),
    }
    atomic_json(output, wrapper)
    write_cost_audit(base, vault, wrapper)
    failure.unlink(missing_ok=True)
    write_markdown(vault, wrapper)
    rebuild_outputs(base, vault)
    return "complete"


def review_existing(vault: Path, paper_id: str, args, recorder: UsageRecorder) -> str:
    base = vault / "rag/paper-memory"
    output = base / "papers" / f"{paper_id}.json"
    if not output.exists():
        return "missing"
    wrapper = json.loads(output.read_text(encoding="utf-8"))
    llm = create_llm_client(recorder, strength=args.model_strength, timeout=args.timeout)
    reviewed, rejected = review_memories(
        llm,
        recorder,
        paper_id,
        wrapper["validated_memories"],
        load_corpus(vault / "rag/corpus.jsonl"),
        args.model_strength,
    )
    wrapper["validated_memories"] = reviewed
    wrapper["rejected_memories"].extend(rejected)
    wrapper["usage"] = usage_for_paper(base / "usage.jsonl", paper_id)
    wrapper["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    atomic_json(output, wrapper)
    write_cost_audit(base, vault, wrapper)
    write_markdown(vault, wrapper)
    rebuild_outputs(base, vault)
    return "reviewed"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path.home() / "auto-research"))
    parser.add_argument("--vault", required=True)
    parser.add_argument("--paper-id", action="append", default=[])
    parser.add_argument("--model-strength", default="medium", choices=["weak", "medium", "strong"])
    parser.add_argument("--part-chars", type=int, default=70000)
    parser.add_argument("--part-memories", type=int, default=20)
    parser.add_argument("--max-memories", type=int, default=32)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--retry-failures", action="store_true")
    parser.add_argument("--review-existing", action="store_true")
    parser.add_argument("--rebuild-from-parts", action="store_true")
    parser.add_argument("--skip-review", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    vault = Path(args.vault)
    if not vault.is_absolute():
        vault = root / vault
    if not vault.is_dir():
        raise SystemExit(f"Vault not found: {vault}")
    all_chars = readable_paper_chars(vault / "rag/corpus.jsonl")
    paper_ids = args.paper_id or sorted(all_chars)
    if args.dry_run:
        for paper_id in paper_ids:
            records = load_records(vault / "rag/corpus.jsonl", paper_id)
            print(
                f"{paper_id}\trecords={len(records)}\tsource_chars={sum(len(str(x['text'])) for x in records)}\t"
                f"parts={len(partition_records(records, args.part_chars)) if records else 0}"
            )
        configured, detail = provider_configured()
        print(f"provider_configured={configured}\tprovider_detail={detail}")
        return 0
    configured, detail = provider_configured()
    if not configured:
        raise SystemExit(detail)
    base = vault / "rag/paper-memory"
    base.mkdir(parents=True, exist_ok=True)
    recorder = UsageRecorder(base / "usage.jsonl")
    counts: Counter[str] = Counter()
    for paper_id in paper_ids:
        result = (
            review_existing(vault, paper_id, args, recorder)
            if args.review_existing
            else run_paper(vault, paper_id, args, recorder)
        )
        counts[result] += 1
        print(f"{paper_id}\t{result}", flush=True)
    print(json.dumps(dict(counts), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
