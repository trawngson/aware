"""Create deterministic visual review sheets for Open Images class mappings."""

from __future__ import annotations

import csv
import hashlib
import json
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from time import sleep
from typing import Any

from PIL import Image, ImageDraw

from .open_images_preflight import CANDIDATE_CLASSES, sha256_file


CVDF_IMAGE_ROOT = "https://open-images-dataset.s3.amazonaws.com"
TILE_WIDTH = 320
TILE_HEIGHT = 240
TILE_HEADER = 32
SHEET_COLUMNS = 4
SHEET_ROWS = 4


def _download_one(
    *,
    split: str,
    image_id: str,
    destination: Path,
    attempts: int = 3,
) -> dict[str, Any]:
    url = f"{CVDF_IMAGE_ROOT}/{split}/{image_id}.jpg"
    part = destination.with_suffix(".jpg.part")
    for attempt in range(1, attempts + 1):
        digest = hashlib.sha256()
        received = 0
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "AWARE-open-images-review/1.0"},
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                with part.open("wb") as handle:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        handle.write(chunk)
                        digest.update(chunk)
                        received += len(chunk)
            part.replace(destination)
            return {
                "image_id": image_id,
                "split": split,
                "url": url,
                "bytes": received,
                "sha256": digest.hexdigest(),
            }
        except Exception:
            if attempt == attempts:
                raise
            sleep(attempt)
    raise AssertionError("unreachable")


def _fit_image(image: Image.Image) -> tuple[Image.Image, int, int]:
    scale = min(TILE_WIDTH / image.width, TILE_HEIGHT / image.height)
    width = max(1, round(image.width * scale))
    height = max(1, round(image.height * scale))
    resized = image.resize((width, height), Image.Resampling.LANCZOS)
    return resized, (TILE_WIDTH - width) // 2, TILE_HEADER + (TILE_HEIGHT - height) // 2


def _render_tile(
    *,
    image_path: Path,
    image_id: str,
    class_name: str,
    boxes: list[tuple[float, float, float, float]],
) -> Image.Image:
    tile = Image.new("RGB", (TILE_WIDTH, TILE_HEADER + TILE_HEIGHT), "white")
    with Image.open(image_path) as source:
        image = source.convert("RGB")
    draw = ImageDraw.Draw(image)
    line_width = max(2, round(max(image.width, image.height) / 300))
    for xmin, xmax, ymin, ymax in boxes:
        draw.rectangle(
            (
                round(xmin * image.width),
                round(ymin * image.height),
                round(xmax * image.width),
                round(ymax * image.height),
            ),
            outline=(255, 0, 0),
            width=line_width,
        )
    resized, x, y = _fit_image(image)
    tile.paste(resized, (x, y))
    label = f"{class_name} | {image_id}"
    ImageDraw.Draw(tile).text((6, 8), label, fill=(0, 0, 0))
    return tile


def create_open_images_review(
    *,
    preflight_directory: str | Path,
    destination: str | Path,
    workers: int = 8,
) -> dict[str, Any]:
    """Download review-only images and produce class-grouped contact sheets."""

    if workers <= 0:
        raise ValueError("workers must be positive")
    preflight = Path(preflight_directory)
    output = Path(destination)
    output.mkdir(parents=True, exist_ok=False)
    images_directory = output / "images"
    sheets_directory = output / "sheets"
    images_directory.mkdir()
    sheets_directory.mkdir()

    filtered = preflight / "filtered"
    with (filtered / "review-selection.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        review_rows = list(csv.DictReader(handle))
    if not review_rows:
        raise ValueError("preflight review selection is empty")

    with (preflight / "official" / "class-descriptions-boxable.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        class_by_mid = {
            row[0]: row[1] for row in csv.reader(handle) if len(row) >= 2
        }

    selected_pairs = {
        (row["ImageID"], row["SourceClass"]) for row in review_rows
    }
    boxes_by_pair: dict[
        tuple[str, str], list[tuple[float, float, float, float]]
    ] = defaultdict(list)
    with (filtered / "selected-boxes.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        for row in csv.DictReader(handle):
            class_name = class_by_mid[row["LabelName"]]
            pair = (row["ImageID"], class_name)
            if pair not in selected_pairs:
                continue
            boxes_by_pair[pair].append(
                (
                    float(row["XMin"]),
                    float(row["XMax"]),
                    float(row["YMin"]),
                    float(row["YMax"]),
                )
            )

    missing_boxes = sorted(selected_pairs - set(boxes_by_pair))
    if missing_boxes:
        raise ValueError(f"review selections missing boxes: {missing_boxes[:5]}")

    split_by_id = {row["ImageID"]: row["Split"] for row in review_rows}
    image_ids = sorted(split_by_id)
    download_records: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _download_one,
                split=split_by_id[image_id],
                image_id=image_id,
                destination=images_directory / f"{image_id}.jpg",
            ): image_id
            for image_id in image_ids
        }
        completed = 0
        for future in as_completed(futures):
            download_records.append(future.result())
            completed += 1
            if completed % 20 == 0 or completed == len(futures):
                print(f"Downloaded review images: {completed}/{len(futures)}")

    sheets: list[Path] = []
    capacity = SHEET_COLUMNS * SHEET_ROWS
    for class_name in CANDIDATE_CLASSES:
        class_rows = [
            row for row in review_rows if row["SourceClass"] == class_name
        ]
        for page_index, start in enumerate(
            range(0, len(class_rows), capacity),
            start=1,
        ):
            page_rows = class_rows[start : start + capacity]
            sheet = Image.new(
                "RGB",
                (
                    SHEET_COLUMNS * TILE_WIDTH,
                    SHEET_ROWS * (TILE_HEADER + TILE_HEIGHT),
                ),
                (225, 225, 225),
            )
            for index, row in enumerate(page_rows):
                tile = _render_tile(
                    image_path=images_directory / f"{row['ImageID']}.jpg",
                    image_id=row["ImageID"],
                    class_name=class_name,
                    boxes=boxes_by_pair[(row["ImageID"], class_name)],
                )
                x = (index % SHEET_COLUMNS) * TILE_WIDTH
                y = (index // SHEET_COLUMNS) * (TILE_HEADER + TILE_HEIGHT)
                sheet.paste(tile, (x, y))
            safe_name = class_name.lower().replace(" ", "-")
            sheet_path = sheets_directory / f"{safe_name}-{page_index:02d}.jpg"
            sheet.save(sheet_path, quality=92, optimize=True)
            sheets.append(sheet_path)

    with Image.open(sheets[0]) as first_sheet:
        composite = Image.new(
            "RGB",
            (
                first_sheet.width,
                first_sheet.height * len(sheets),
            ),
            "white",
        )
    for index, sheet_path in enumerate(sheets):
        with Image.open(sheet_path) as sheet:
            composite.paste(sheet, (0, index * sheet.height))
    complete_path = output / "open-images-complete-review.jpg"
    composite.save(complete_path, quality=90, optimize=True)

    report = {
        "schema_version": "1.0",
        "source": "open-images-v7-waste-subset",
        "review_rows": len(review_rows),
        "unique_images": len(image_ids),
        "download_bytes": sum(item["bytes"] for item in download_records),
        "downloads": sorted(
            download_records,
            key=lambda item: item["image_id"],
        ),
        "sheets": [
            {"path": path.name, "sha256": sha256_file(path)}
            for path in sheets
        ],
        "complete_review": {
            "path": complete_path.name,
            "sha256": sha256_file(complete_path),
        },
    }
    with (output / "review-manifest.json").open(
        "x", encoding="utf-8"
    ) as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return report
