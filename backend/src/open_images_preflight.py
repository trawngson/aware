"""Metadata-only Open Images subset preflight.

This module filters official Open Images CSV files without downloading images.
It produces a deterministic review list, source counts, attribution checks, and
content hashes before any pixel acquisition is approved.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


CANDIDATE_CLASSES = ("Bottle", "Box", "Plastic bag", "Tin can")
DISALLOWED_REVIEW_ATTRIBUTES = ("IsGroupOf", "IsDepiction", "IsInside")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _deterministic_sample(
    image_ids: Iterable[str],
    *,
    class_name: str,
    seed: int,
    limit: int,
) -> list[str]:
    unique = set(image_ids)
    return sorted(
        unique,
        key=lambda image_id: hashlib.sha256(
            f"{seed}:{class_name}:{image_id}".encode("utf-8")
        ).hexdigest(),
    )[:limit]


def build_open_images_preflight(
    *,
    class_descriptions_file: str | Path,
    boxes_file: str | Path,
    image_metadata_file: str | Path,
    destination: str | Path,
    split: str = "validation",
    sample_per_class: int = 48,
    seed: int = 26,
    source_urls: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Filter candidate metadata and write a deterministic preflight release."""

    if sample_per_class <= 0:
        raise ValueError("sample_per_class must be positive")
    if seed < 0:
        raise ValueError("seed must be non-negative")

    output = Path(destination)
    output.mkdir(parents=True, exist_ok=False)

    with Path(class_descriptions_file).open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        class_by_mid = {
            row[0]: row[1]
            for row in csv.reader(handle)
            if len(row) >= 2
        }
    mid_by_class = {name: mid for mid, name in class_by_mid.items()}
    missing_classes = sorted(set(CANDIDATE_CLASSES) - set(mid_by_class))
    if missing_classes:
        raise ValueError(f"missing candidate classes: {missing_classes}")
    candidate_mids = {mid_by_class[name] for name in CANDIDATE_CLASSES}

    selected_boxes_path = output / "selected-boxes.csv"
    box_counts: Counter[str] = Counter()
    review_eligible_counts: Counter[str] = Counter()
    selected_image_ids: set[str] = set()
    eligible_image_ids: dict[str, set[str]] = defaultdict(set)
    rejected_attribute_counts: Counter[str] = Counter()

    with Path(boxes_file).open("r", encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames is None:
            raise ValueError("box annotation CSV has no header")
        with selected_boxes_path.open("x", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=reader.fieldnames)
            writer.writeheader()
            for row in reader:
                mid = row.get("LabelName", "")
                if mid not in candidate_mids:
                    continue
                class_name = class_by_mid[mid]
                image_id = row["ImageID"]
                writer.writerow(row)
                box_counts[class_name] += 1
                selected_image_ids.add(image_id)

                disallowed = [
                    field
                    for field in DISALLOWED_REVIEW_ATTRIBUTES
                    if row.get(field, "0") == "1"
                ]
                if disallowed:
                    for field in disallowed:
                        rejected_attribute_counts[field] += 1
                    continue
                review_eligible_counts[class_name] += 1
                eligible_image_ids[class_name].add(image_id)

    selected_metadata_path = output / "selected-image-metadata.csv"
    metadata_image_ids: set[str] = set()
    total_original_bytes = 0
    missing_original_size = 0
    missing_author = 0
    license_counts: Counter[str] = Counter()

    with Path(image_metadata_file).open(
        "r", encoding="utf-8", newline=""
    ) as source:
        reader = csv.DictReader(source)
        if reader.fieldnames is None:
            raise ValueError("image metadata CSV has no header")
        with selected_metadata_path.open(
            "x", encoding="utf-8", newline=""
        ) as target:
            writer = csv.DictWriter(target, fieldnames=reader.fieldnames)
            writer.writeheader()
            for row in reader:
                image_id = row.get("ImageID", "")
                if image_id not in selected_image_ids:
                    continue
                writer.writerow(row)
                metadata_image_ids.add(image_id)
                if not row.get("Author", "").strip():
                    missing_author += 1
                license_counts[row.get("License", "").strip() or "<missing>"] += 1
                try:
                    total_original_bytes += int(row["OriginalSize"])
                except (KeyError, TypeError, ValueError):
                    missing_original_size += 1

    missing_metadata = sorted(selected_image_ids - metadata_image_ids)
    if missing_metadata:
        raise ValueError(
            f"missing image metadata for {len(missing_metadata)} selected images"
        )

    review_rows: list[dict[str, str]] = []
    for class_name in CANDIDATE_CLASSES:
        for image_id in _deterministic_sample(
            eligible_image_ids[class_name],
            class_name=class_name,
            seed=seed,
            limit=sample_per_class,
        ):
            review_rows.append(
                {
                    "Split": split,
                    "ImageID": image_id,
                    "SourceClass": class_name,
                }
            )

    review_selection_path = output / "review-selection.csv"
    with review_selection_path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("Split", "ImageID", "SourceClass"),
        )
        writer.writeheader()
        writer.writerows(review_rows)

    review_ids_path = output / "review-image-ids.txt"
    review_ids = sorted({row["ImageID"] for row in review_rows})
    with review_ids_path.open("x", encoding="utf-8") as handle:
        for image_id in review_ids:
            handle.write(f"{split}/{image_id}\n")

    report: dict[str, Any] = {
        "schema_version": "1.0",
        "source": "open-images-v7-waste-subset",
        "split": split,
        "seed": seed,
        "sample_per_class": sample_per_class,
        "candidate_class_mids": {
            name: mid_by_class[name] for name in CANDIDATE_CLASSES
        },
        "box_counts": dict(sorted(box_counts.items())),
        "review_eligible_box_counts": dict(
            sorted(review_eligible_counts.items())
        ),
        "selected_image_count": len(selected_image_ids),
        "review_image_count": len(review_ids),
        "review_rows_by_class": dict(
            sorted(Counter(row["SourceClass"] for row in review_rows).items())
        ),
        "rejected_review_attributes": dict(
            sorted(rejected_attribute_counts.items())
        ),
        "attribution": {
            "missing_author_count": missing_author,
            "missing_original_size_count": missing_original_size,
            "license_counts": dict(sorted(license_counts.items())),
        },
        "estimated_original_image_bytes": total_original_bytes,
        "estimated_original_image_gib": round(
            total_original_bytes / (1024**3), 3
        ),
        "source_urls": source_urls or {},
    }
    report["output_sha256"] = {
        path.name: sha256_file(path)
        for path in (
            selected_boxes_path,
            selected_metadata_path,
            review_selection_path,
            review_ids_path,
        )
    }

    report_path = output / "preflight-report.json"
    with report_path.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return report
