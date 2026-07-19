#!/usr/bin/env python3
import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": "Mozilla/5.0 (AutoResearch fulltext acquisition; scholarly metadata preservation)"
}


def safe_slug(s: str, max_len: int = 80) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", s.lower()).strip("-")
    return slug[:max_len].strip("-") or "paper"


def arxiv_pdf_url(url: str) -> str | None:
    patterns = [
        r"arxiv\.org/abs/([0-9]{4}\.[0-9]{4,5})(?:v\d+)?",
        r"arxiv\.org/pdf/([0-9]{4}\.[0-9]{4,5})(?:v\d+)?",
        r"10\.48550/arxiv\.([0-9]{4}\.[0-9]{4,5})(?:v\d+)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, url, re.I)
        if match:
            return f"https://arxiv.org/pdf/{match.group(1)}"
    return None


def acl_pdf_url(url: str) -> str | None:
    match = re.search(r"aclanthology\.org/([0-9]{4}\.[^/]+)/?", url)
    if match:
        return f"https://aclanthology.org/{match.group(1)}.pdf"
    doi = doi_from_url(url)
    if doi and doi.lower().startswith("10.18653/v1/"):
        return f"https://aclanthology.org/{doi.split('/', 2)[-1]}.pdf"
    return None


def doi_from_url(url: str) -> str | None:
    match = re.search(r"doi\.org/(10\.\d{4,9}/.+)$", url, re.I)
    if not match:
        return None
    return match.group(1).strip().rstrip(".")


def direct_pdf_url(url: str) -> str | None:
    if re.search(r"\.pdf($|[?#])", url, re.I):
        return url
    return None


def get(url: str, timeout: int) -> requests.Response:
    return requests.get(url, headers=HEADERS, timeout=(5, timeout), allow_redirects=True)


def discover_pdf_from_html(url: str, timeout: int) -> tuple[str | None, str | None]:
    try:
        resp = get(url, timeout)
    except Exception as exc:
        return None, f"html-fetch-error:{type(exc).__name__}"
    content_type = resp.headers.get("content-type", "")
    if "pdf" in content_type.lower():
        return resp.url, None
    if resp.status_code >= 400:
        return None, f"html-http-{resp.status_code}"
    text = resp.text
    soup = BeautifulSoup(text, "html.parser")
    selectors = [
        ("meta", {"name": "citation_pdf_url"}),
        ("meta", {"property": "citation_pdf_url"}),
        ("meta", {"name": "bepress_citation_pdf_url"}),
    ]
    for name, attrs in selectors:
        tag = soup.find(name, attrs=attrs)
        if tag and tag.get("content"):
            return urljoin(resp.url, tag["content"]), None
    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        label = " ".join(tag.get_text(" ").split()).lower()
        if re.search(r"\.pdf($|[?#])", href, re.I) or label in {"pdf", "download pdf", "view pdf"} or "pdf" in label:
            return urljoin(resp.url, href), None
    return None, "no-pdf-link-found"


def candidate_pdf_urls(url: str, timeout: int, quick: bool) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    for label, fn in [("direct-pdf", direct_pdf_url), ("arxiv", arxiv_pdf_url), ("acl", acl_pdf_url)]:
        pdf = fn(url)
        if pdf:
            candidates.append((label, pdf))
    if not quick:
        discovered, reason = discover_pdf_from_html(url, timeout)
        if discovered:
            candidates.append(("html-discovered", discovered))
    return candidates


def download_pdf(url: str, path: Path, timeout: int) -> tuple[bool, str]:
    try:
        resp = get(url, timeout)
    except Exception as exc:
        return False, f"pdf-fetch-error:{type(exc).__name__}"
    if resp.status_code >= 400:
        return False, f"pdf-http-{resp.status_code}"
    content_type = resp.headers.get("content-type", "").lower()
    body = resp.content
    if b"%PDF" not in body[:2048] and "pdf" not in content_type:
        return False, f"not-pdf:{content_type or 'unknown-content-type'}"
    path.write_bytes(body)
    return True, "ok"


def pdftotext(pdf: Path, txt: Path, timeout: int) -> tuple[bool, str, int, int]:
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf), str(txt)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
    except Exception as exc:
        return False, f"pdftotext-error:{type(exc).__name__}", 0, 0
    if result.returncode != 0:
        return False, f"pdftotext-exit-{result.returncode}:{result.stderr.strip()[:120]}", 0, 0
    text = txt.read_text(errors="ignore") if txt.exists() else ""
    lines = len([line for line in text.splitlines() if line.strip()])
    words = len(text.split())
    if words < 300:
        return False, "text-too-short-or-scanned", lines, words
    return True, "ok", lines, words


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path.home() / "auto-research"))
    parser.add_argument("--vault", action="append", help="Specific vault path. Repeatable.")
    parser.add_argument("--skip-vault", action="append", default=[])
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--quick", action="store_true", help="Only try direct PDF, arXiv, and ACL URLs; skip slow DOI HTML discovery.")
    parser.add_argument("--limit", type=int, help="Process only the first N rows per vault, for testing.")
    args = parser.parse_args()

    root = Path(args.root)
    if args.vault:
        vaults = [Path(v) for v in args.vault]
    else:
        vaults = sorted(root.glob("Postgraduate_*"))
    skip = set(args.skip_vault)

    for vault in vaults:
        if vault.name in skip:
            continue
        master_files = sorted((vault / "wiki/papers").glob("*paper-master.csv"))
        if not master_files:
            continue
        pdf_dir = vault / ".raw/fulltext-pdfs"
        txt_dir = vault / ".raw/fulltext-text"
        html_dir = vault / ".raw/fulltext-html"
        pdf_dir.mkdir(parents=True, exist_ok=True)
        txt_dir.mkdir(parents=True, exist_ok=True)
        html_dir.mkdir(parents=True, exist_ok=True)
        status_rows = []
        for master in master_files:
            for idx, row in enumerate(csv.DictReader(master.open()), start=1):
                if args.limit and idx > args.limit:
                    break
                pid = row["id"]
                title = row["title"]
                url = row.get("url", "")
                slug = f"{pid}-{safe_slug(title)}"
                pdf_path = pdf_dir / f"{slug}.pdf"
                txt_path = txt_dir / f"{slug}.txt"
                result = {
                    "id": pid,
                    "title": title,
                    "url": url,
                    "status": "fulltext-blocked",
                    "pdf": "",
                    "text": "",
                    "reason": "no-candidate-pdf",
                    "lines": "0",
                    "words": "0",
                }
                if txt_path.exists() and len(txt_path.read_text(errors="ignore").split()) >= 300:
                    text = txt_path.read_text(errors="ignore")
                    result.update(status="fulltext-read", pdf=str(pdf_path.relative_to(vault)) if pdf_path.exists() else "", text=str(txt_path.relative_to(vault)), reason="existing-text", lines=str(len([l for l in text.splitlines() if l.strip()])), words=str(len(text.split())))
                    status_rows.append(result)
                    print(f"{vault.name}\t{pid}\texisting-text", flush=True)
                    continue
                reasons = []
                for label, candidate in candidate_pdf_urls(url, args.timeout, args.quick):
                    ok, reason = download_pdf(candidate, pdf_path, args.timeout)
                    if not ok:
                        reasons.append(f"{label}:{reason}")
                        continue
                    ok_text, text_reason, lines, words = pdftotext(pdf_path, txt_path, args.timeout)
                    if ok_text:
                        result.update(status="fulltext-read", pdf=str(pdf_path.relative_to(vault)), text=str(txt_path.relative_to(vault)), reason=f"{label}:{candidate}", lines=str(lines), words=str(words))
                        print(f"{vault.name}\t{pid}\tfulltext-read\t{label}\twords={words}", flush=True)
                        break
                    reasons.append(f"{label}:{text_reason}")
                else:
                    result["reason"] = "; ".join(reasons) if reasons else "no-candidate-pdf"
                    print(f"{vault.name}\t{pid}\tblocked\t{result['reason'][:120]}", flush=True)
                status_rows.append(result)
        status_csv = vault / ".raw/fulltext-status.csv"
        with status_csv.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["id", "title", "url", "status", "pdf", "text", "reason", "lines", "words"])
            writer.writeheader()
            writer.writerows(status_rows)
        read = sum(1 for row in status_rows if row["status"] == "fulltext-read")
        blocked = len(status_rows) - read
        print(f"{vault.name}\tread={read}\tblocked={blocked}\tstatus={status_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
