#!/usr/bin/env python3
"""
Extract class-labeled point annotations from lydia_drawing.pdf.

The client PDF stores class points as numbered overlays on separate pages:
- Page 3: yellow labels (Penguin in Burrow), IDs 1..48
- Page 5: blue labels (Penguin Deep in Burrow), IDs 1..11
- Page 6: green labels (Empty Burrow), IDs 1..63

Coordinates are extracted from `pdftotext -bbox-layout` word boxes, then
converted from PDF page points to the embedded screenshot pixel space.
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


PAGE_CLASS_MAP = {
    3: "Penguin in Burrow",
    5: "Penguin Deep in Burrow",
    6: "Empty Burrow",
}


@dataclass
class LabelPoint:
    label: str
    label_id: int
    page: int
    x_pdf: float
    y_pdf: float
    x_img: float
    y_img: float


def _extract_numeric_words(pdf_path: Path, page: int) -> list[tuple[int, float, float]]:
    out = subprocess.check_output(
        [
            "pdftotext",
            "-f",
            str(page),
            "-l",
            str(page),
            "-bbox-layout",
            str(pdf_path),
            "-",
        ],
        text=True,
    )

    root = ET.fromstring(out)
    items: list[tuple[int, float, float]] = []
    for node in root.iter():
        if not node.tag.endswith("word"):
            continue
        text = (node.text or "").strip()
        if not re.fullmatch(r"\d+", text):
            continue
        x_min = float(node.attrib["xMin"])
        x_max = float(node.attrib["xMax"])
        y_min = float(node.attrib["yMin"])
        y_max = float(node.attrib["yMax"])
        x_center = (x_min + x_max) / 2.0
        y_center = (y_min + y_max) / 2.0
        items.append((int(text), x_center, y_center))

    return sorted(items, key=lambda r: r[0])


def extract_labels(
    pdf_path: Path,
    scale: float,
    y_offset: float,
) -> list[LabelPoint]:
    points: list[LabelPoint] = []

    for page, label_name in PAGE_CLASS_MAP.items():
        words = _extract_numeric_words(pdf_path, page)
        for label_id, x_pdf, y_pdf in words:
            x_img = x_pdf / scale
            y_img = (y_pdf - y_offset) / scale
            points.append(
                LabelPoint(
                    label=label_name,
                    label_id=label_id,
                    page=page,
                    x_pdf=x_pdf,
                    y_pdf=y_pdf,
                    x_img=x_img,
                    y_img=y_img,
                )
            )

    return points


def write_outputs(
    points: list[LabelPoint],
    out_meta_csv: Path,
    out_legacy_csv: Path,
    image_name: str,
    image_width: int,
    image_height: int,
) -> None:
    out_meta_csv.parent.mkdir(parents=True, exist_ok=True)
    out_legacy_csv.parent.mkdir(parents=True, exist_ok=True)

    with out_meta_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "label",
                "label_id",
                "page",
                "x_pdf",
                "y_pdf",
                "x_img",
                "y_img",
                "image",
                "image_width",
                "image_height",
            ]
        )
        for p in points:
            w.writerow(
                [
                    p.label,
                    p.label_id,
                    p.page,
                    f"{p.x_pdf:.6f}",
                    f"{p.y_pdf:.6f}",
                    f"{p.x_img:.2f}",
                    f"{p.y_img:.2f}",
                    image_name,
                    image_width,
                    image_height,
                ]
            )

    # Legacy schema used by existing thermal label tooling:
    # label, x, y, image, width, height (no header)
    with out_legacy_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for p in points:
            w.writerow(
                [
                    p.label,
                    int(round(p.x_img)),
                    int(round(p.y_img)),
                    image_name,
                    image_width,
                    image_height,
                ]
            )


def write_qc_overlay(points: list[LabelPoint], base_image: Path, out_png: Path) -> None:
    from PIL import Image, ImageDraw

    color_map = {
        "Penguin in Burrow": (255, 220, 0),
        "Penguin Deep in Burrow": (70, 150, 255),
        "Empty Burrow": (80, 220, 80),
    }

    img = Image.open(base_image).convert("RGB")
    draw = ImageDraw.Draw(img)
    for p in points:
        color = color_map.get(p.label, (255, 255, 255))
        r = 6
        draw.ellipse((p.x_img - r, p.y_img - r, p.x_img + r, p.y_img + r), outline=color, width=2)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pdf",
        type=Path,
        default=Path("new-to-process/images_box2/lydia_drawing.pdf"),
        help="Path to lydia_drawing.pdf",
    )
    parser.add_argument(
        "--out-meta-csv",
        type=Path,
        default=Path("data/interim/lydia_box2/labels_extracted_meta.csv"),
        help="Output CSV with IDs/pages and floating-point coordinates",
    )
    parser.add_argument(
        "--out-legacy-csv",
        type=Path,
        default=Path("data/interim/lydia_box2/labels_extracted_legacy.csv"),
        help="Output CSV in legacy thermal label schema",
    )
    parser.add_argument(
        "--image-name",
        default="lydia_drawing_base_1640x2360.png",
        help="Image name used in output rows",
    )
    parser.add_argument(
        "--image-width",
        type=int,
        default=1640,
        help="Embedded screenshot width in pixels",
    )
    parser.add_argument(
        "--image-height",
        type=int,
        default=2360,
        help="Embedded screenshot height in pixels",
    )
    parser.add_argument(
        "--pdf-to-image-scale",
        type=float,
        default=0.305085,
        help="Scale from image pixel coords to PDF coords",
    )
    parser.add_argument(
        "--pdf-y-offset",
        type=float,
        default=72.0,
        help="PDF y-offset where image starts",
    )
    parser.add_argument(
        "--base-image",
        type=Path,
        default=None,
        help="Optional base screenshot image (1640x2360) for QC overlay",
    )
    parser.add_argument(
        "--out-qc-png",
        type=Path,
        default=None,
        help="Optional QC overlay output path (requires --base-image)",
    )
    args = parser.parse_args()

    points = extract_labels(
        pdf_path=args.pdf,
        scale=args.pdf_to_image_scale,
        y_offset=args.pdf_y_offset,
    )
    write_outputs(
        points=points,
        out_meta_csv=args.out_meta_csv,
        out_legacy_csv=args.out_legacy_csv,
        image_name=args.image_name,
        image_width=args.image_width,
        image_height=args.image_height,
    )

    class_counts: dict[str, int] = {}
    for p in points:
        class_counts[p.label] = class_counts.get(p.label, 0) + 1

    print(f"Extracted {len(points)} labels from {args.pdf}")
    for label, n in sorted(class_counts.items()):
        print(f"  - {label}: {n}")
    print(f"Wrote: {args.out_meta_csv}")
    print(f"Wrote: {args.out_legacy_csv}")

    if args.base_image and args.out_qc_png:
        write_qc_overlay(points=points, base_image=args.base_image, out_png=args.out_qc_png)
        print(f"Wrote: {args.out_qc_png}")


if __name__ == "__main__":
    main()
