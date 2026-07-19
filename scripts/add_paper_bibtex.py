#!/usr/bin/env python3
import argparse
import csv
import re
import time
import urllib.request
from pathlib import Path


def fetch(url: str, accept: str | None, timeout: int) -> str | None:
    headers = {"User-Agent": "Mozilla/5.0"}
    if accept:
        headers["Accept"] = accept
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace").strip()
            if body.startswith("@"):
                return body
    except Exception:
        return None
    return None


def arxiv_id(url: str) -> str | None:
    for pattern in [
        r"arxiv\.org/abs/([0-9]{4}\.[0-9]{4,5})(?:v\d+)?",
        r"10\.48550/arxiv\.([0-9]{4}\.[0-9]{4,5})(?:v\d+)?",
    ]:
        match = re.search(pattern, url, re.I)
        if match:
            return match.group(1)
    return None


def doi_from_url(url: str) -> str | None:
    match = re.search(r"doi\.org/(10\.\d{4,9}/.+)$", url, re.I)
    if not match:
        return None
    return match.group(1).strip().rstrip(".")


def acl_id(url: str) -> str | None:
    match = re.search(r"aclanthology\.org/([0-9]{4}\.[^/]+)/?", url)
    if match:
        return match.group(1)
    doi = doi_from_url(url)
    if doi and doi.lower().startswith("10.18653/v1/"):
        return doi.split("/", 2)[-1]
    return None


def slug_key(pid: str, title: str, year: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", title.lower())
    core = "".join(words[:3]) or pid.lower()
    return f"{pid.lower()}_{core}_{year}"


def fallback_bibtex(row: dict[str, str]) -> str:
    venue = row.get("venue", "")
    lower = venue.lower()
    entry_type = "misc"
    if any(token in lower for token in ["conference", "emnlp", "acl", "chi", "koli", "findings"]):
        entry_type = "inproceedings"
    elif venue:
        entry_type = "article"
    fields = [
        f"  title = {{{row['title']}}}",
        f"  year = {{{row['year']}}}",
    ]
    if venue:
        target = "booktitle" if entry_type == "inproceedings" else "journal"
        fields.append(f"  {target} = {{{venue}}}")
    if row.get("url"):
        fields.append(f"  url = {{{row['url']}}}")
    fields.append("  note = {AutoResearch fallback BibTeX generated from local paper master; verify before formal citation}")
    return "@%s{%s,\n%s\n}" % (entry_type, slug_key(row["id"], row["title"], row["year"]), ",\n".join(fields))


def get_bibtex(row: dict[str, str], network: bool, timeout: int) -> tuple[str, str]:
    url = row.get("url", "").strip()
    if network:
        aid = acl_id(url)
        if aid:
            bib = fetch(f"https://aclanthology.org/{aid}.bib", None, timeout)
            if bib:
                return bib, "acl"
        arx = arxiv_id(url)
        if arx:
            bib = fetch(f"https://arxiv.org/bibtex/{arx}", None, timeout)
            if bib:
                return bib, "arxiv"
        doi = doi_from_url(url)
        if doi:
            bib = fetch(f"https://doi.org/{doi}", "application/x-bibtex", timeout)
            if bib:
                return bib, "doi"
    return fallback_bibtex(row), "fallback"


def normalize_bibtex(bib: str) -> str:
    return "\n".join(line.rstrip() for line in bib.replace("\r\n", "\n").replace("\r", "\n").strip().splitlines())


def yaml_literal(key: str, value: str) -> str:
    body = "\n".join("  " + line if line else "" for line in value.splitlines())
    return f"{key}: |\n{body}"


def upsert_frontmatter(path: Path, key: str, value: str) -> None:
    text = path.read_text()
    if not text.startswith("---\n"):
        raise RuntimeError(f"missing frontmatter: {path}")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise RuntimeError(f"unterminated frontmatter: {path}")
    fm = text[4:end]
    body = text[end:]
    literal = yaml_literal(key, value)
    pattern = re.compile(rf"^{re.escape(key)}:\s*\|\n(?:^[ \t].*\n?|\n)*", re.M)
    if pattern.search(fm):
        fm = pattern.sub(literal + "\n", fm)
    else:
        if not fm.endswith("\n"):
            fm += "\n"
        fm += literal + "\n"
    path.write_text("---\n" + fm + body)


def find_master_files(vault: Path, explicit_master: str | None) -> list[Path]:
    if explicit_master:
        master = Path(explicit_master)
        if not master.is_absolute():
            master = vault / master
        return [master]
    return sorted((vault / "wiki" / "papers").glob("*paper-master.csv"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Add or refresh YAML BibTeX fields in AutoResearch paper cards.")
    parser.add_argument("--vault", required=True, type=Path, help="Path to a Postgraduate_* vault.")
    parser.add_argument("--master", help="Optional paper-master CSV path, absolute or relative to vault.")
    parser.add_argument("--sleep", type=float, default=0.2, help="Delay between network requests.")
    parser.add_argument("--timeout", type=int, default=18, help="Per-request network timeout in seconds.")
    parser.add_argument("--no-network", action="store_true", help="Use only fallback BibTeX from paper-master rows.")
    args = parser.parse_args()

    vault = args.vault.expanduser().resolve()
    masters = find_master_files(vault, args.master)
    if not masters:
        raise SystemExit(f"No paper-master CSV found under {vault}/wiki/papers")

    counts: dict[str, int] = {"acl": 0, "arxiv": 0, "doi": 0, "fallback": 0}
    updated = 0
    for master in masters:
        with master.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        for row in rows:
            pid = row["id"]
            matches = sorted((vault / "wiki" / "papers").glob(f"{pid}-*.md"))
            if len(matches) != 1:
                raise RuntimeError(f"expected one paper card for {pid}, found {len(matches)}")
            bib, source = get_bibtex(row, not args.no_network, args.timeout)
            upsert_frontmatter(matches[0], "bibtex", normalize_bibtex(bib))
            counts[source] += 1
            updated += 1
            if not args.no_network:
                time.sleep(args.sleep)
    print(f"updated={updated} acl={counts['acl']} arxiv={counts['arxiv']} doi={counts['doi']} fallback={counts['fallback']}")


if __name__ == "__main__":
    main()
