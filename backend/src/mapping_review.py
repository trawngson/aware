"""Deterministic visual-review sheets for source-to-ontology mappings."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .canonical_data import safe_relative_path


@dataclass(frozen=True)
class ReviewSample:
    source_class: str
    annotation_id: str
    relative_path: str
    bbox: tuple[float, float, float, float]


def select_review_samples(
    document: Mapping[str, Any],
    source_classes: Iterable[str],
    *,
    seed: int,
    samples_per_class: int,
) -> dict[str, tuple[ReviewSample, ...]]:
    """Select stable annotation examples without relying on input ordering."""

    if seed < 0:
        raise ValueError("seed must be non-negative")
    if samples_per_class < 1:
        raise ValueError("samples_per_class must be positive")

    categories = {
        int(item["id"]): str(item["name"]) for item in document["categories"]
    }
    images = {
        int(item["id"]): safe_relative_path(str(item["file_name"]))
        for item in document["images"]
    }
    requested = set(source_classes)
    grouped: dict[str, list[ReviewSample]] = defaultdict(list)
    for annotation in document["annotations"]:
        source_class = categories[int(annotation["category_id"])]
        if source_class not in requested:
            continue
        grouped[source_class].append(
            ReviewSample(
                source_class=source_class,
                annotation_id=str(annotation["id"]),
                relative_path=images[int(annotation["image_id"])],
                bbox=tuple(float(value) for value in annotation["bbox"]),
            )
        )

    selected: dict[str, tuple[ReviewSample, ...]] = {}
    for source_class in sorted(requested):
        ranked = sorted(
            grouped.get(source_class, ()),
            key=lambda sample: hashlib.sha256(
                f"{seed}:{source_class}:{sample.annotation_id}".encode("utf-8")
            ).digest(),
        )
        selected[source_class] = tuple(ranked[:samples_per_class])
    return selected


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        raise ValueError(f"source class cannot form a filename: {value!r}")
    return slug


def _focused_crop(image: Any, bbox: Sequence[float]) -> tuple[Any, tuple[float, ...]]:
    x, y, width, height = bbox
    if width <= 0 or height <= 0:
        raise ValueError(f"invalid review box: {tuple(bbox)}")
    center_x = x + width / 2
    center_y = y + height / 2
    crop_width = min(image.width, max(width * 2.5, min(256, image.width)))
    crop_height = min(image.height, max(height * 2.5, min(256, image.height)))
    left = max(0.0, min(center_x - crop_width / 2, image.width - crop_width))
    top = max(0.0, min(center_y - crop_height / 2, image.height - crop_height))
    right = left + crop_width
    bottom = top + crop_height
    crop = image.crop((round(left), round(top), round(right), round(bottom)))
    return crop, (x - left, y - top, x + width - left, y + height - top)


def render_review_sheets(
    samples_by_class: Mapping[str, Sequence[ReviewSample]],
    image_root: str | Path,
    destination: str | Path,
    *,
    target_classes: Mapping[str, str] | None = None,
    columns: int = 4,
    tile_size: tuple[int, int] = (360, 300),
) -> tuple[Path, ...]:
    """Render one PNG per source class plus an HTML index."""

    from PIL import Image, ImageDraw, ImageFont, ImageOps

    if columns < 1:
        raise ValueError("columns must be positive")
    root = Path(image_root)
    output = Path(destination)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite mapping review: {output}")
    output.mkdir(parents=True, exist_ok=False)

    font = ImageFont.load_default()
    tile_width, tile_height = tile_size
    rendered: list[Path] = []
    index_entries: list[tuple[str, str, int]] = []
    for source_class in sorted(samples_by_class):
        samples = samples_by_class[source_class]
        target_class = (
            target_classes.get(source_class, "") if target_classes is not None else ""
        )
        mapping_title = (
            f"{source_class} -> {target_class}" if target_class else source_class
        )
        rows = max(1, (len(samples) + columns - 1) // columns)
        title_height = 36
        sheet = Image.new(
            "RGB",
            (columns * tile_width, title_height + rows * tile_height),
            "white",
        )
        draw = ImageDraw.Draw(sheet)
        draw.text(
            (10, 10),
            f"{mapping_title} — {len(samples)} deterministic samples",
            fill="black",
            font=font,
        )

        for index, sample in enumerate(samples):
            column = index % columns
            row = index // columns
            tile_x = column * tile_width
            tile_y = title_height + row * tile_height
            image_path = root / sample.relative_path
            with Image.open(image_path) as source:
                oriented = ImageOps.exif_transpose(source).convert("RGB")
            crop, box_in_crop = _focused_crop(oriented, sample.bbox)
            available_width = tile_width - 20
            available_height = tile_height - 42
            scale = min(
                available_width / crop.width,
                available_height / crop.height,
            )
            resized_size = (
                max(1, round(crop.width * scale)),
                max(1, round(crop.height * scale)),
            )
            resized = crop.resize(resized_size, Image.Resampling.LANCZOS)
            offset_x = tile_x + (tile_width - resized.width) // 2
            offset_y = tile_y + 4
            sheet.paste(resized, (offset_x, offset_y))
            scaled_box = tuple(value * scale for value in box_in_crop)
            draw.rectangle(
                (
                    offset_x + scaled_box[0],
                    offset_y + scaled_box[1],
                    offset_x + scaled_box[2],
                    offset_y + scaled_box[3],
                ),
                outline=(255, 0, 0),
                width=3,
            )
            caption = f"{sample.relative_path} | annotation {sample.annotation_id}"
            draw.text(
                (tile_x + 6, tile_y + tile_height - 28),
                caption[:58],
                fill="black",
                font=font,
            )

        filename = f"{_slug(source_class)}.png"
        path = output / filename
        sheet.save(path, format="PNG")
        rendered.append(path)
        index_entries.append((mapping_title, filename, len(samples)))

    html = [
        "<!doctype html>",
        '<meta charset="utf-8">',
        "<title>TACO safe-mapping review</title>",
        "<h1>TACO safe-mapping review</h1>",
        "<p>Red rectangles mark source annotations. Raw images are unchanged.</p>",
    ]
    for source_class, filename, count in index_entries:
        html.extend(
            [
                f"<h2>{escape(source_class)} ({count})</h2>",
                f'<img src="{escape(filename)}" '
                'style="max-width:100%;height:auto" loading="lazy">',
            ]
        )
    (output / "index.html").write_text("\n".join(html) + "\n", encoding="utf-8")
    return tuple(rendered)


def load_coco_document(path: str | Path) -> Mapping[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
