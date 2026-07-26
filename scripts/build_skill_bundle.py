#!/usr/bin/env python3
"""Build a deterministic, redistributable Your AI Postgraduate Skill bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INCLUDE_FILES = {
    "VERSION",
    "LICENSE",
    "README.md",
    "README_EN.md",
    "README_CN.md",
    "requirements.txt",
    "auth.example",
    "install.sh",
}
INCLUDE_DIRS = ("skills", "scripts", "templates", "integrations", "docs/assets", "tools", "tests")
EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", ".git"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
PREFIX = "Your_AI_Postgraduate"


def included_files() -> list[Path]:
    files = [ROOT / name for name in sorted(INCLUDE_FILES)]
    for directory in INCLUDE_DIRS:
        base = ROOT / directory
        files.extend(path for path in base.rglob("*") if path.is_file())
    return sorted(
        {
            path
            for path in files
            if path.exists()
            and not EXCLUDED_PARTS.intersection(path.parts)
            and path.suffix not in EXCLUDED_SUFFIXES
        },
        key=lambda path: path.relative_to(ROOT).as_posix(),
    )


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def zip_info(name: str, executable: bool = False) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    mode = 0o755 if executable else 0o644
    info.external_attr = (stat.S_IFREG | mode) << 16
    return info


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "release")
    args = parser.parse_args()
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    archive = args.output_dir / f"your-ai-postgraduate-skills-v{version}.zip"

    manifest_files = []
    payloads: list[tuple[str, bytes, bool]] = []
    for path in included_files():
        relative = path.relative_to(ROOT).as_posix()
        data = path.read_bytes()
        executable = relative == "install.sh" or relative.endswith(".sh")
        payloads.append((relative, data, executable))
        manifest_files.append({"path": relative, "sha256": digest(data), "bytes": len(data)})

    manifest = {
        "name": "Your AI Postgraduate Skill Bundle",
        "version": version,
        "license": "MIT",
        "entry_skill": "skills/your-ai-postgraduate/SKILL.md",
        "skill_count": sum(1 for path, _, _ in payloads if path.endswith("/SKILL.md")),
        "files": manifest_files,
    }
    manifest_data = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for relative, data, executable in payloads:
            bundle.writestr(zip_info(f"{PREFIX}/{relative}", executable), data)
        bundle.writestr(zip_info(f"{PREFIX}/bundle-manifest.json"), manifest_data)

    checksum = digest(archive.read_bytes())
    checksum_file = args.output_dir / "SHA256SUMS"
    checksum_file.write_text(f"{checksum}  {archive.name}\n", encoding="ascii")
    print(f"Built {archive} ({archive.stat().st_size} bytes, {manifest['skill_count']} skills)")
    print(f"SHA256 {checksum}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
