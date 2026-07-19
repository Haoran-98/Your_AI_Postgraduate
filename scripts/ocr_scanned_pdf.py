#!/usr/bin/env python3
"""OCR an image-only PDF into page-delimited UTF-8 text."""

from __future__ import annotations

import argparse
from pathlib import Path

import fitz
import numpy as np
from rapidocr_onnxruntime import RapidOCR


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--dpi", type=int, default=220)
    args = parser.parse_args()

    engine = RapidOCR()
    document = fitz.open(args.pdf)
    pages: list[str] = []
    scale = args.dpi / 72
    matrix = fitz.Matrix(scale, scale)

    for page_number, page in enumerate(document, start=1):
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
            pixmap.height, pixmap.width, pixmap.n
        )
        result, _ = engine(image)
        lines = [] if not result else [str(item[1]).strip() for item in result if str(item[1]).strip()]
        pages.append("\n".join(lines))
        print(f"page={page_number}/{len(document)}\tlines={len(lines)}", flush=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n\f\n".join(pages).strip() + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
