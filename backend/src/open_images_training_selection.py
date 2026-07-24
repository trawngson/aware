"""Select approved Open Images training metadata without downloading pixels."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .open_images_preflight import sha256_file


APPROVED_CLASS_MAPPINGS = {
    "Plastic bag": "plastic_bag",
    "Tin can": "metal_can",
}
EXCLUDED_ATTRIBUTES = ("IsGroupOf", "IsDepiction", "IsInside")


def _valid_normalized_box(row: dict[str, str]) -> bool:
    try:
        xmin = float(row["XMin"])
        xmax = float(row["XMax"])
        ymin = float(row["YMin"])
        ymax = float(row["YMax"])
    except (KeyError, TypeError, ValueError):
        return False
    return (
        0 <= xmin < xmax <= 1
        and 0 <= ymin < ymax <= 1
    )


def select_open_images_training_metadata(
    *,
    class_descriptions_file: str | Path,
    boxes_file: str | Path,
    image_metadata_file: str | Path,
    destination: str | Path,
    source_urls: dict[str, str],
) -> dict[str, Any]:
    """Write an immutable approved-label subset and selection report."""

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
    missing = sorted(set(APPROVED_CLASS_MAPPINGS) - set(mid_by_class))
    if missing:
        raise ValueError(f"approved Open Images classes are missing: {missing}")
    approved_mids = {
        mid_by_class[name]: name for name in APPROVED_CLASS_MAPPINGS
    }

    candidate_boxes_path = output / "candidate-boxes-before-attribution.csv"
    candidate_image_ids: set[str] = set()
    candidate_box_counts: Counter[str] = Counter()
    excluded_attribute_counts: Counter[str] = Counter()
    invalid_box_counts: Counter[str] = Counter()

    print("Filtering approved Open Images training boxes", flush=True)
    with Path(boxes_file).open("r", encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames is None:
            raise ValueError("training box CSV has no header")
        with candidate_boxes_path.open(
            "x", encoding="utf-8", newline=""
        ) as target:
            writer = csv.DictWriter(target, fieldnames=reader.fieldnames)
            writer.writeheader()
            for row_number, row in enumerate(reader, start=2):
                if row_number % 1_000_000 == 0:
                    print(
                        f"Scanned training box rows: {row_number:,}",
                        flush=True,
                    )
                source_class = approved_mids.get(row.get("LabelName", ""))
                if source_class is None:
                    continue
                excluded = [
                    field
                    for field in EXCLUDED_ATTRIBUTES
                    if row.get(field, "0") == "1"
                ]
                if excluded:
                    for field in excluded:
                        excluded_attribute_counts[field] += 1
                    continue
                if not _valid_normalized_box(row):
                    invalid_box_counts[source_class] += 1
                    continue
                writer.writerow(row)
                image_id = row["ImageID"]
                candidate_image_ids.add(image_id)
                candidate_box_counts[source_class] += 1

    candidate_metadata_path = output / "candidate-source-metadata.csv"
    selected_metadata_path = output / "selected-source-metadata.csv"
    found_candidate_image_ids: set[str] = set()
    eligible_image_ids: set[str] = set()
    license_counts: Counter[str] = Counter()
    rejected_attribution_counts: Counter[str] = Counter()
    missing_size_count = 0
    total_original_bytes = 0

    print("Filtering attribution metadata for selected images", flush=True)
    with Path(image_metadata_file).open(
        "r", encoding="utf-8", newline=""
    ) as source:
        reader = csv.DictReader(source)
        if reader.fieldnames is None:
            raise ValueError("training image metadata CSV has no header")
        with candidate_metadata_path.open(
            "x", encoding="utf-8", newline=""
        ) as candidate_target, selected_metadata_path.open(
            "x", encoding="utf-8", newline=""
        ) as selected_target:
            candidate_writer = csv.DictWriter(
                candidate_target, fieldnames=reader.fieldnames
            )
            selected_writer = csv.DictWriter(
                selected_target, fieldnames=reader.fieldnames
            )
            candidate_writer.writeheader()
            selected_writer.writeheader()
            for row_number, row in enumerate(reader, start=2):
                if row_number % 250_000 == 0:
                    print(
                        f"Scanned image metadata rows: {row_number:,}",
                        flush=True,
                    )
                image_id = row.get("ImageID", "")
                if image_id not in candidate_image_ids:
                    continue
                candidate_writer.writerow(row)
                found_candidate_image_ids.add(image_id)
                author = row.get("Author", "").strip()
                license_url = row.get("License", "").strip()
                license_counts[license_url or "<missing>"] += 1
                if not author:
                    rejected_attribution_counts["missing_author"] += 1
                    continue
                if not license_url.startswith(
                    "https://creativecommons.org/licenses/by/2.0"
                ):
                    rejected_attribution_counts["unapproved_license"] += 1
                    continue
                selected_writer.writerow(row)
                eligible_image_ids.add(image_id)
                try:
                    total_original_bytes += int(row["OriginalSize"])
                except (KeyError, TypeError, ValueError):
                    missing_size_count += 1

    missing_metadata = sorted(candidate_image_ids - found_candidate_image_ids)
    if missing_metadata:
        raise ValueError(
            f"metadata missing for {len(missing_metadata)} selected images"
        )

    selected_boxes_path = output / "selected-boxes.csv"
    selected_image_ids: set[str] = set()
    image_ids_by_class: dict[str, set[str]] = defaultdict(set)
    selected_box_counts: Counter[str] = Counter()
    with candidate_boxes_path.open(
        "r", encoding="utf-8", newline=""
    ) as source:
        reader = csv.DictReader(source)
        if reader.fieldnames is None:
            raise ValueError("candidate box CSV has no header")
        with selected_boxes_path.open(
            "x", encoding="utf-8", newline=""
        ) as target:
            writer = csv.DictWriter(target, fieldnames=reader.fieldnames)
            writer.writeheader()
            for row in reader:
                image_id = row["ImageID"]
                if image_id not in eligible_image_ids:
                    continue
                source_class = class_by_mid[row["LabelName"]]
                writer.writerow(row)
                selected_image_ids.add(image_id)
                image_ids_by_class[source_class].add(image_id)
                selected_box_counts[source_class] += 1

    missing_selected_classes = sorted(
        set(APPROVED_CLASS_MAPPINGS) - set(selected_box_counts)
    )
    if missing_selected_classes:
        raise ValueError(
            "no eligible training boxes remain for approved classes: "
            f"{missing_selected_classes}"
        )

    image_ids_path = output / "image-ids.txt"
    with image_ids_path.open("x", encoding="utf-8") as handle:
        for image_id in sorted(selected_image_ids):
            handle.write(f"train/{image_id}\n")

    report: dict[str, Any] = {
        "schema_version": "1.0",
        "source": "open-images-v7-waste-subset",
        "split": "train",
        "approved_class_mappings": APPROVED_CLASS_MAPPINGS,
        "source_class_mids": {
            name: mid_by_class[name] for name in APPROVED_CLASS_MAPPINGS
        },
        "candidate_box_counts_before_attribution": dict(
            sorted(candidate_box_counts.items())
        ),
        "selected_box_counts": dict(sorted(selected_box_counts.items())),
        "selected_image_counts_by_class": {
            name: len(image_ids_by_class[name])
            for name in sorted(APPROVED_CLASS_MAPPINGS)
        },
        "selected_unique_image_count": len(selected_image_ids),
        "excluded_attribute_counts": dict(
            sorted(excluded_attribute_counts.items())
        ),
        "invalid_box_counts": dict(sorted(invalid_box_counts.items())),
        "attribution": {
            "license_counts": dict(sorted(license_counts.items())),
            "rejected_counts": dict(
                sorted(rejected_attribution_counts.items())
            ),
            "missing_original_size_count": missing_size_count,
        },
        "estimated_original_bytes": total_original_bytes,
        "estimated_original_gib": round(total_original_bytes / (1024**3), 3),
        "source_urls": source_urls,
    }
    print("Hashing immutable official source metadata", flush=True)
    report["source_sha256"] = {
        "class_descriptions": sha256_file(class_descriptions_file),
        "boxes": sha256_file(boxes_file),
        "image_metadata": sha256_file(image_metadata_file),
    }
    report["output_sha256"] = {
        path.name: sha256_file(path)
        for path in (
            candidate_boxes_path,
            candidate_metadata_path,
            selected_boxes_path,
            selected_metadata_path,
            image_ids_path,
        )
    }
    with (output / "selection-report.json").open(
        "x", encoding="utf-8"
    ) as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return report
