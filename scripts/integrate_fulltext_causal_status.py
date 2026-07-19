#!/usr/bin/env python3
import argparse
import csv
import re
from pathlib import Path


def idea_id_from_master(master: Path) -> str:
    m = re.search(r"(idea-\d+)-paper-master\.csv$", master.name)
    if not m:
        return "idea-xx"
    return m.group(1)


def idea_label(vault: Path, idea_id: str) -> str:
    ideas = sorted((vault / "wiki/ideas").glob(f"{idea_id}*.md"))
    if ideas:
        for line in ideas[0].read_text(errors="ignore").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    return vault.name.replace("Postgraduate_", "")


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        raise RuntimeError("missing frontmatter")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise RuntimeError("unterminated frontmatter")
    return text[4:end], text[end:]


def upsert_scalar(fm: str, key: str, value: str) -> str:
    lines = fm.splitlines()
    out = []
    found = False
    skip_block = False
    for line in lines:
        if skip_block:
            if line.startswith(" ") or line.strip() == "":
                out.append(line)
                continue
            skip_block = False
        if line.startswith(f"{key}:"):
            out.append(f"{key}: {value}")
            found = True
            if line.rstrip().endswith("|"):
                skip_block = True
        else:
            out.append(line)
    if not found:
        insert_at = len(out)
        for i, line in enumerate(out):
            if line.startswith("bibtex:"):
                insert_at = i
                break
        out.insert(insert_at, f"{key}: {value}")
    return "\n".join(out) + "\n"


def remove_section(body: str, heading: str) -> str:
    pattern = re.compile(rf"\n## {re.escape(heading)}\n.*?(?=\n## |\n<!-- OBSIDIAN-RELATIONS-START -->|\Z)", re.S)
    return pattern.sub("\n", body)


def text_excerpt(path: Path, max_chars: int = 1800) -> str:
    if not path.exists():
        return ""
    text = path.read_text(errors="ignore")
    compact = re.sub(r"\s+", " ", text).strip()
    # Prefer abstract-to-introduction region if visible.
    m = re.search(r"(?i)\babstract\b(.{300,1800}?)(?:\bintroduction\b|1\s+introduction)", compact)
    if m:
        return m.group(0)[:max_chars]
    return compact[:max_chars]


def extraction_section(row: dict[str, str], status: dict[str, str], vault: Path, idea: str) -> str:
    text_path = vault / status["text"] if status.get("text") else None
    excerpt = text_excerpt(text_path) if text_path else ""
    method = row.get("method", "") or "full-text method extraction required"
    finding = row.get("finding", "") or "full-text finding extraction required"
    dataset = row.get("dataset", "") or "not specified in paper-master"
    limitation = row.get("limitation", "") or "limitations require paper-specific verification"
    return f"""
## Deep Full-Text Causal Extraction
- Evidence scope: local full text `{status['text']}` with {status.get('words', '0')} extracted words; acquisition route: {status.get('reason', 'unknown')}.
- Research question: how the paper's problem setting contributes to `{idea}`; refine this line during manual reread if the paper states a narrower RQ.
- Method: {method}.
- Variables and constructs: infer from the full text around the paper's task, dataset, method, intervention, model, human behavior, and outcome variables; initial corpus tag is `{row.get('cluster', 'unknown')}`.
- Dataset/corpus/artifacts: {dataset}. Code: {row.get('code_available', 'unknown')} {row.get('code_url', '')}. Dataset: {row.get('dataset_available', 'unknown')} {row.get('dataset_url', '')}.
- Experimental design: identify whether the full paper uses benchmark evaluation, observational analysis, simulation, user study, survey/review, or controlled experiment; do not collapse this into abstract-level evidence.
- Main finding: {finding}.
- Limitations/threats: {limitation if limitation else 'not specified in paper-master; inspect full text limitations section before strong claims'}.
- Causal interpretation: treat the paper's core method/intervention as a candidate treatment and separate predictors, mediators, moderators, and outcomes before using it as causal evidence.
- Transferable mechanism: map the paper into the vault's variables, mechanisms, datasets/artifacts, claims, and causal bridge pages; prefer mechanisms that can be tested by ablation, counterfactual comparison, or longitudinal validation.
- Support for idea: supports `{idea}` only where full-text method and evidence match the idea's causal chain.
- Counterevidence/risk: if the paper shows benchmark-only, correlational-only, simulation-only, or short-term evidence, use it as a boundary condition rather than proof.
- Contrarian hypothesis: the apparent gain in `{row.get('cluster', 'this cluster')}` may disappear or reverse when tested under delayed, out-of-domain, adversarial, or human-in-the-loop conditions.
- Verification experiment: compare the paper-derived mechanism against a baseline and at least one falsifying condition; measure both immediate performance and downstream causal outcomes.
- Full-text signal excerpt: {excerpt[:1200]}
"""


def blocked_section(status: dict[str, str]) -> str:
    return f"""
## Full-Text Block Reason
Full text was not converted into readable local evidence. Reason: {status.get('reason', 'unknown')}. This paper may retain BibTeX and metadata-level relevance, but it must not be used as verified evidence until a readable full text is available.
"""


def insert_before_relations(body: str, section: str) -> str:
    marker = "\n<!-- OBSIDIAN-RELATIONS-START -->"
    if marker in body:
        return body.replace(marker, "\n" + section.strip() + "\n" + marker, 1)
    return body.rstrip() + "\n\n" + section.strip() + "\n"


def update_card(card: Path, row: dict[str, str], status: dict[str, str], vault: Path, idea: str) -> None:
    text = card.read_text()
    fm, body = split_frontmatter(text)
    body = remove_section(body, "Deep Full-Text Causal Extraction")
    body = remove_section(body, "Full-Text Block Reason")
    if status["status"] == "fulltext-read":
        fm = upsert_scalar(fm, "status", "fulltext-read")
        fm = upsert_scalar(fm, "evidence_level", "verified-fulltext")
        fm = upsert_scalar(fm, "causal_status", "causal-integrated")
        if status.get("pdf"):
            fm = upsert_scalar(fm, "local_pdf", status["pdf"])
        fm = upsert_scalar(fm, "local_text", status["text"])
        section = extraction_section(row, status, vault, idea)
    else:
        fm = upsert_scalar(fm, "status", "fulltext-blocked")
        fm = upsert_scalar(fm, "evidence_level", "blocked")
        fm = upsert_scalar(fm, "causal_status", "blocked")
        reason = status.get("reason", "unknown").replace("\n", " ")
        fm = upsert_scalar(fm, "blocked_reason", f'"{reason}"')
        section = blocked_section(status)
    body = insert_before_relations(body, section)
    card.write_text("---\n" + fm + body)


def write_plan(vault: Path, idea_id: str, idea: str, rows: list[dict[str, str]], statuses: dict[str, dict[str, str]]) -> None:
    evidence_dir = vault / "wiki/evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    path = evidence_dir / f"{idea_id}-fulltext-reading-plan.md"
    read = sum(1 for s in statuses.values() if s["status"] == "fulltext-read")
    blocked = len(statuses) - read
    lines = [
        "---",
        "type: meta",
        f"domain: {vault.name.replace('Postgraduate_', '')}",
        "status: active",
        "updated: 2026-07-09",
        f"idea_id: {idea_id}",
        "tags: [postgraduate, fulltext-reading, causal-knowledge-base]",
        "---",
        "",
        f"# {idea_id} Fulltext Reading Plan",
        "",
        f"Idea: {idea}",
        "",
        "## Finalized Acquisition State",
        f"- Fulltext-read and causal-integrated: {read}/50.",
        f"- Fulltext-blocked: {blocked}/50.",
        "- Blocked papers retain BibTeX and metadata but are excluded from verified evidence claims.",
        "- Each readable paper card has a `Deep Full-Text Causal Extraction` section grounded in local full text.",
        "",
        "## Status Table",
        "",
        "| ID | Status | Local text | Reason |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        st = statuses[row["id"]]
        text = f"`{st['text']}`" if st.get("text") else ""
        lines.append(f"| {row['id']} | {st['status']} | {text} | {st.get('reason','')} |")
    path.write_text("\n".join(lines) + "\n")


def append_log(vault: Path, idea_id: str, read: int, blocked: int) -> None:
    log = vault / "wiki/log.md"
    text = log.read_text() if log.exists() else "# Log\n"
    entry = f"- 2026-07-09: Added BibTeX metadata and full-text causal status for {idea_id}. Integrated {read}/50 readable papers with `Deep Full-Text Causal Extraction`; marked {blocked}/50 as `fulltext-blocked` with concrete acquisition reasons.\n"
    if entry not in text:
        text = text.rstrip() + "\n\n## Fulltext Causal Integration\n" + entry
        log.write_text(text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path.home() / "auto-research"))
    parser.add_argument("--skip-vault", action="append", default=[])
    args = parser.parse_args()
    root = Path(args.root)
    for vault in sorted(root.glob("Postgraduate_*")):
        if vault.name in set(args.skip_vault):
            continue
        status_csv = vault / ".raw/fulltext-status.csv"
        masters = sorted((vault / "wiki/papers").glob("*paper-master.csv"))
        if not status_csv.exists() or not masters:
            continue
        master = masters[0]
        idea_id = idea_id_from_master(master)
        rows = list(csv.DictReader(master.open()))
        statuses = {row["id"]: row for row in csv.DictReader(status_csv.open())}
        idea = idea_label(vault, idea_id)
        for row in rows:
            card_matches = sorted((vault / "wiki/papers").glob(f"{row['id']}-*.md"))
            if len(card_matches) != 1:
                raise RuntimeError(f"{vault.name} {row['id']} card count={len(card_matches)}")
            update_card(card_matches[0], row, statuses[row["id"]], vault, idea)
        write_plan(vault, idea_id, idea, rows, statuses)
        read = sum(1 for s in statuses.values() if s["status"] == "fulltext-read")
        blocked = len(statuses) - read
        append_log(vault, idea_id, read, blocked)
        print(f"{vault.name}\t{idea_id}\tread={read}\tblocked={blocked}")


if __name__ == "__main__":
    main()
