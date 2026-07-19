#!/usr/bin/env python3
"""Run resumable, token-audited Hyper-Extract over provenance-rich chunks."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from hyperextract_clients import (
    UsageRecorder,
    create_hyperextract_clients,
    create_llm_client,
    provider_configured,
)


DEFAULT_PRIORITY_SECTIONS = ("method", "experiment", "evaluation", "result", "limitation", "threat")


def load_records(
    path: Path,
    source_types: set[str],
    paper_ids: set[str],
    record_ids: set[str],
    limit: int | None,
) -> list[dict[str, object]]:
    records = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            metadata = item.get("metadata", {})
            if source_types and metadata.get("source_type") not in source_types:
                continue
            if paper_ids and metadata.get("paper_id") not in paper_ids:
                continue
            if record_ids and item.get("id") not in record_ids:
                continue
            if metadata.get("rag_evidence_level") == "blocked":
                continue
            records.append(item)
            if limit and len(records) >= limit:
                break
    return records


def coalesce_records(records: list[dict[str, object]], max_chars: int) -> list[dict[str, object]]:
    merged: list[dict[str, object]] = []
    current: list[dict[str, object]] = []
    current_chars = 0

    def flush() -> None:
        nonlocal current_chars
        if not current:
            return
        first, last = current[0], current[-1]
        metadata = dict(first["metadata"])
        merged.append(
            {
                "id": f"{first['id']}..{last['id']}" if len(current) > 1 else first["id"],
                "text": "\n\n".join(str(item["text"]) for item in current),
                "metadata": metadata,
                "segments": [
                    {
                        "id": str(item["id"]),
                        "text": str(item["text"]),
                        "page": item["metadata"].get("page"),
                        "section": item["metadata"].get("section"),
                    }
                    for item in current
                ],
            }
        )
        current.clear()
        current_chars = 0

    for item in records:
        same_paper = not current or item["metadata"].get("paper_id") == current[0]["metadata"].get("paper_id")
        item_chars = len(str(item["text"]))
        if current and (not same_paper or current_chars + item_chars > max_chars):
            flush()
        current.append(item)
        current_chars += item_chars
    flush()
    return merged


def render_input(record: dict[str, object]) -> str:
    metadata = record["metadata"]
    lines = [
        "[SOURCE_METADATA]",
        f"SOURCE_ID: {metadata.get('paper_id') or 'unknown'}",
        f"TITLE: {metadata.get('title') or 'unknown'}",
        f"VAULT: {metadata.get('vault') or 'unknown'}",
        "REVIEW_STATUS: machine-extracted",
        "[/SOURCE_METADATA]",
    ]
    for segment in record["segments"]:
        page = segment.get("page") if segment.get("page") is not None else "unknown"
        section = segment.get("section") or "unknown"
        chunk_id = segment["id"]
        lines.extend(
            [
                "",
                "[SOURCE_CHUNK]",
                f"PAGE: {page}",
                f"SECTION: {section}",
                f"CHUNK_ID: {chunk_id}",
                f"LOCATION: {metadata.get('paper_id')}|page={page}|section={section}|chunk={chunk_id}",
                "[TEXT]",
                str(segment["text"]),
                "[/TEXT]",
                "[/SOURCE_CHUNK]",
            ]
        )
    return "\n".join(lines)


def selected_vaults(root: Path, requested: list[str]) -> list[Path]:
    if not requested:
        return sorted(path for path in root.glob("Postgraduate_*") if path.is_dir())
    vaults = []
    for value in requested:
        path = Path(value)
        if not path.is_absolute():
            path = root / value
        if not path.is_dir():
            raise SystemExit(f"Vault not found: {path}")
        vaults.append(path)
    return vaults


def unit_path(base: Path, mode: str, unit_id: str) -> Path:
    digest = hashlib.sha256(unit_id.encode()).hexdigest()[:20]
    return base / "chunks" / mode / f"{digest}.json"


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def priority_units(
    records: list[dict[str, object]], patterns: list[str], max_per_paper: int
) -> set[str]:
    selected: set[str] = set()
    counts: Counter[str] = Counter()
    for item in records:
        paper_id = str(item["metadata"].get("paper_id") or "unknown")
        sections = " ".join(str(segment.get("section") or "") for segment in item["segments"]).lower()
        if counts[paper_id] < max_per_paper and any(pattern.lower() in sections for pattern in patterns):
            selected.add(str(item["id"]))
            counts[paper_id] += 1
    return selected


def run_unit(
    template,
    item: dict[str, object],
    mode: str,
    base: Path,
    recorder: UsageRecorder,
    retry_failures: bool,
    engine_chunk_size: int,
) -> str:
    output = unit_path(base, mode, str(item["id"]))
    failure = unit_path(base / "failures", mode, str(item["id"]))
    if output.exists():
        return "skipped-success"
    if failure.exists() and not retry_failures:
        return "skipped-failure"
    previous_attempt = json.loads(failure.read_text()).get("attempt", 0) if failure.exists() else 0
    attempt = int(previous_attempt) + 1
    rendered = render_input(item)
    if len(rendered) > engine_chunk_size:
        raise ValueError(
            f"Rendered unit exceeds engine chunk size ({len(rendered)} > {engine_chunk_size}): {item['id']}"
        )
    context = {
        "unit_id": item["id"],
        "paper_id": item["metadata"].get("paper_id"),
        "mode": mode,
        "model_strength": "weak" if mode == "one-stage" else "medium",
        "attempt": attempt,
    }
    recorder.set_context(**context)
    started = time.monotonic()
    try:
        partial = template.parse(rendered)
    except Exception as exc:
        atomic_json(
            failure,
            {
                **context,
                "status": "failed",
                "elapsed_s": round(time.monotonic() - started, 3),
                "error_type": type(exc).__name__,
                "error": str(exc)[:2000],
            },
        )
        return "failed"
    atomic_json(
        output,
        {
            **context,
            "status": "complete",
            "elapsed_s": round(time.monotonic() - started, 3),
            "source_chunk_ids": [segment["id"] for segment in item["segments"]],
            "source_chars": len(str(item["text"])),
            "rendered_chars": len(rendered),
            "graph": partial.data.model_dump(),
        },
    )
    failure.unlink(missing_ok=True)
    return "complete"


def usage_summary(path: Path) -> dict[str, object]:
    totals: Counter[str] = Counter()
    by_mode: dict[str, Counter[str]] = {}
    group_counts: Counter[tuple[str, str, int]] = Counter()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            mode = str(row.get("mode") or "unknown")
            group = (
                str(row.get("unit_id") or "unknown"),
                mode,
                int(row.get("attempt") or 1),
            )
            group_counts[group] += 1
            expected_for_group = 2 if mode == "two-stage" else 1
            request_kind = "expected" if group_counts[group] <= expected_for_group else "unexpected"
            bucket = by_mode.setdefault(mode, Counter())
            for key in ("input_tokens", "output_tokens", "total_tokens", "input_chars", "output_chars"):
                value = int(row.get(key) or 0)
                totals[key] += value
                bucket[key] += value
                totals[f"{request_kind}_{key}"] += value
                bucket[f"{request_kind}_{key}"] += value
            totals["requests"] += 1
            bucket["requests"] += 1
            totals[f"{request_kind}_requests"] += 1
            bucket[f"{request_kind}_requests"] += 1
            if row.get("status") == "error":
                totals["errors"] += 1
                bucket["errors"] += 1
    totals["logical_extractions"] = len(group_counts)
    totals["unexpected_requests"] = totals["unexpected_requests"]
    return {**dict(totals), "by_mode": {key: dict(value) for key, value in by_mode.items()}}


def aggregate_graph(base: Path, knowledge_abstract: Path, language: str) -> tuple[int, int]:
    nodes: dict[str, tuple[int, dict[str, object]]] = {}
    edges: dict[str, tuple[int, dict[str, object]]] = {}
    files = [
        *((base / "chunks/one-stage").glob("*.json") if (base / "chunks/one-stage").exists() else []),
        *((base / "chunks/two-stage").glob("*.json") if (base / "chunks/two-stage").exists() else []),
    ]
    for path in sorted(files):
        wrapper = json.loads(path.read_text(encoding="utf-8"))
        priority = 1 if wrapper.get("mode") == "two-stage" else 0
        graph = wrapper["graph"]
        for node in graph.get("nodes", []):
            key = str(node.get("name"))
            previous = nodes.get(key)
            if previous is None or priority > previous[0] or float(node.get("confidence", 0)) > float(previous[1].get("confidence", 0)):
                nodes[key] = (priority, node)
        for edge in graph.get("edges", []):
            key = "|".join(str(edge.get(field, "")) for field in ("source", "type", "target", "source_id"))
            previous = edges.get(key)
            if previous is None or priority > previous[0] or float(edge.get("confidence", 0)) > float(previous[1].get("confidence", 0)):
                edges[key] = (priority, edge)
    node_values = [value for _, value in nodes.values()]
    node_names = {node.get("name") for node in node_values}
    edge_values = [
        value
        for _, value in edges.values()
        if value.get("source") in node_names and value.get("target") in node_names
    ]
    knowledge_abstract.mkdir(parents=True, exist_ok=True)
    atomic_json(knowledge_abstract / "data.json", {"nodes": node_values, "edges": edge_values})
    atomic_json(
        knowledge_abstract / "metadata.json",
        {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "template": "academic_causal_evidence_graph",
            "lang": language,
            "type": "graph",
        },
    )
    return len(node_values), len(edge_values)


def write_cost_audit(
    base: Path,
    usage: dict[str, object],
    selected_records: list[dict[str, object]],
    all_records: list[dict[str, object]],
    elapsed_s: float,
) -> None:
    selected_chars = sum(len(str(item["text"])) for item in selected_records)
    all_chars = sum(len(str(item["text"])) for item in all_records)
    selected_papers = len({item["metadata"].get("paper_id") for item in selected_records}) or 1
    all_papers = len({item["metadata"].get("paper_id") for item in all_records})
    char_factor = all_chars / selected_chars if selected_chars else 0
    paper_factor = all_papers / selected_papers
    projected: Counter[str] = Counter()
    observed_requests: Counter[str] = Counter()
    for mode, totals in usage.get("by_mode", {}).items():
        factor = paper_factor if mode == "two-stage" else char_factor
        successful_requests = max(
            int(totals.get("expected_requests", totals.get("requests", 0)))
            - int(totals.get("errors", 0)),
            0,
        )
        projected["requests"] += round(successful_requests * factor)
        observed_requests["requests"] += round(
            int(totals.get("expected_requests", totals.get("requests", 0))) * factor
        )
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            projected[key] += round(
                int(totals.get(f"expected_{key}", totals.get(key, 0))) * factor
            )
    previous_elapsed = 0.0
    run_attempts = 1
    audit_path = base / "cost-audit.json"
    if audit_path.exists():
        previous = json.loads(audit_path.read_text(encoding="utf-8"))
        previous_elapsed = float(previous.get("actual", {}).get("elapsed_s", 0))
        run_attempts = int(previous.get("actual", {}).get("run_attempts", 1)) + 1
    atomic_json(
        audit_path,
        {
            "actual": {
                **usage,
                "elapsed_s": round(previous_elapsed + elapsed_s, 3),
                "run_attempts": run_attempts,
                "source_chars": selected_chars,
                "timeout_or_error_token_usage_may_be_unreported": bool(usage.get("errors")),
            },
            "projection": {
                "eligible_fulltext_papers": all_papers,
                "requested_papers": 50,
                "blocked_without_fulltext": 50 - all_papers,
                "eligible_source_chars": all_chars,
                "character_scale_factor": round(char_factor, 4),
                "paper_scale_factor": round(paper_factor, 4),
                **dict(projected),
                "observed_requests_including_failure_pattern": observed_requests["requests"],
                "monetary_cost": None,
                "note": "Planned requests exclude failed attempts; observed request projection includes the audit failure pattern. Error responses may omit billable provider token usage.",
            },
        },
    )


def process_vault(vault: Path, template_path: Path, language: str, args) -> None:
    from hyperextract import Template
    from ontomem.merger import MergeStrategy

    corpus = vault / "rag/corpus.jsonl"
    all_records = load_records(corpus, set(args.source_type), set(), set(), None)
    source_records = load_records(
        corpus, set(args.source_type), set(args.paper_id), set(args.record_id), args.limit
    )
    units = coalesce_records(source_records, args.unit_chars)
    reviews = set() if args.no_two_stage_review else priority_units(
        units, args.priority_section or list(DEFAULT_PRIORITY_SECTIONS), args.max_two_stage_reviews_per_paper
    )
    base = vault / "rag/hyperextract"
    if args.force and base.exists():
        shutil.rmtree(base)
    if base.exists() and not (args.resume or args.force or args.retry_failures):
        raise SystemExit(f"Output exists: {base}. Use --resume, --retry-failures, or --force.")
    base.mkdir(parents=True, exist_ok=True)
    usage_path = base / "usage.jsonl"
    recorder = UsageRecorder(usage_path)
    one_stage_llm, embedder = create_hyperextract_clients(recorder, strength="weak")
    two_stage_llm = create_llm_client(recorder, strength="medium")
    common = {
        "embedder": embedder,
        "chunk_size": args.engine_chunk_size,
        "chunk_overlap": 0,
        "max_workers": 1,
        "node_strategy_or_merger": MergeStrategy.KEEP_EXISTING,
        "edge_strategy_or_merger": MergeStrategy.KEEP_EXISTING,
    }
    one_stage = Template.create(
        str(template_path),
        language,
        llm_client=one_stage_llm,
        extraction_mode="one_stage",
        **common,
    )
    two_stage = Template.create(
        str(template_path),
        language,
        llm_client=two_stage_llm,
        extraction_mode="two_stage",
        **common,
    )
    started = time.monotonic()
    counts: Counter[str] = Counter()

    for index, item in enumerate(units, start=1):
        result = run_unit(
            one_stage, item, "one-stage", base, recorder, args.retry_failures, args.engine_chunk_size
        )
        counts[f"one-stage:{result}"] += 1
        if str(item["id"]) in reviews and result in {"complete", "skipped-success"}:
            review_result = run_unit(
                two_stage, item, "two-stage", base, recorder, args.retry_failures, args.engine_chunk_size
            )
            counts[f"two-stage:{review_result}"] += 1
        progress = {
            "vault": vault.name,
            "units_total": len(units),
            "one_stage_complete": counts["one-stage:complete"] + counts["one-stage:skipped-success"],
            "one_stage_failed": counts["one-stage:failed"] + counts["one-stage:skipped-failure"],
            "two_stage_targets": len(reviews),
            "two_stage_complete": counts["two-stage:complete"] + counts["two-stage:skipped-success"],
            "two_stage_failed": counts["two-stage:failed"] + counts["two-stage:skipped-failure"],
            "current_unit": item["id"],
            "usage": usage_summary(usage_path),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        atomic_json(base / "progress.json", progress)
        print(
            f"{vault.name}\tunit={index}/{len(units)}\tone_stage={result}\t"
            f"tokens={progress['usage'].get('total_tokens', 0)}",
            flush=True,
        )

    nodes, edges = aggregate_graph(base, base / "knowledge-abstract", language)
    successful_ids = [
        json.loads(path.read_text())["unit_id"]
        for path in sorted((base / "chunks/one-stage").glob("*.json"))
    ]
    atomic_json(base / "processed_ids.json", sorted(successful_ids))
    usage = usage_summary(usage_path)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "vault": vault.name,
        "template": str(template_path),
        "paper_ids": sorted(set(args.paper_id)),
        "source_records": len(source_records),
        "extraction_units": len(units),
        "unit_chars": args.unit_chars,
        "engine_chunk_size": args.engine_chunk_size,
        "concurrency": 1,
        "sdk_retries": 0,
        "automatic_unit_retries": 0,
        "deterministic_internal_merge": "keep_existing",
        "model_strengths": {
            "one_stage": "weak",
            "two_stage_review": "medium",
            "rag_and_final_reasoning": "strong",
        },
        "one_stage_default": True,
        "two_stage_review_targets": len(reviews),
        "nodes": nodes,
        "edges": edges,
        "usage": usage,
    }
    atomic_json(base / "run-manifest.json", manifest)
    if len(set(args.paper_id)) == 1:
        write_cost_audit(base, usage, source_records, all_records, time.monotonic() - started)

    if not args.skip_index or not args.skip_obsidian:
        ka = Template.create(
            str(template_path),
            language,
            llm_client=one_stage_llm,
            extraction_mode="one_stage",
            **common,
        )
        ka.load(base / "knowledge-abstract")
        if not args.skip_index:
            ka.build_index()
            ka.dump(base / "knowledge-abstract")
        if not args.skip_obsidian:
            obsidian = base / "obsidian"
            if obsidian.exists():
                shutil.rmtree(obsidian)
            ka.export_obsidian(obsidian, vault_name=f"{vault.name} Hyper-Extract Evidence Graph", overwrite=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path.home() / "auto-research"))
    parser.add_argument("--vault", action="append", default=[])
    parser.add_argument("--template", default="integrations/hyperextract/academic_causal_evidence_graph.yaml")
    parser.add_argument("--language", default="en", choices=["en", "zh"])
    parser.add_argument("--source-type", action="append", default=["paper-fulltext"])
    parser.add_argument("--paper-id", action="append", default=[])
    parser.add_argument("--record-id", action="append", default=[])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--unit-chars", type=int, default=6000)
    parser.add_argument("--engine-chunk-size", type=int, default=20000)
    parser.add_argument("--priority-section", action="append")
    parser.add_argument("--max-two-stage-reviews-per-paper", type=int, default=4)
    parser.add_argument("--no-two-stage-review", action="store_true")
    parser.add_argument("--retry-failures", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--skip-index", action="store_true")
    parser.add_argument("--skip-obsidian", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    template_path = Path(args.template)
    if not template_path.is_absolute():
        template_path = root / template_path
    vaults = selected_vaults(root, args.vault)
    if args.dry_run:
        for vault in vaults:
            records = load_records(
                vault / "rag/corpus.jsonl",
                set(args.source_type),
                set(args.paper_id),
                set(args.record_id),
                args.limit,
            )
            units = coalesce_records(records, args.unit_chars)
            reviews = set() if args.no_two_stage_review else priority_units(
                units,
                args.priority_section or list(DEFAULT_PRIORITY_SECTIONS),
                args.max_two_stage_reviews_per_paper,
            )
            max_rendered = max((len(render_input(item)) for item in units), default=0)
            print(
                f"{vault.name}\trecords={len(records)}\tunits={len(units)}\t"
                f"two_stage_reviews={len(reviews)}\tmax_rendered_chars={max_rendered}"
            )
        configured, detail = provider_configured()
        print(f"provider_configured={configured}\tprovider_detail={detail}")
        return 0
    configured, detail = provider_configured()
    if not configured:
        raise SystemExit(detail)
    for vault in vaults:
        process_vault(vault, template_path, args.language, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
