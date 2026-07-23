"""Deterministic adapters for the two approved v1 training sources."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .box_policy import minimum_size_review_reason
from .canonical_data import (
    CanonicalAnnotation,
    CanonicalImage,
    ExclusionEvent,
    NormalizedBox,
    safe_relative_path,
)
from .metadata_validation import EXPECTED_CLASSES
from .mappings import MappingDecision, MappingTable


@dataclass(frozen=True)
class AdaptationResult:
    images: tuple[CanonicalImage, ...]
    exclusions: tuple[ExclusionEvent, ...]


def _mapped_class_id(decision: MappingDecision) -> int:
    if decision.canonical_class is None:
        raise ValueError("included mapping must have a canonical class")
    return EXPECTED_CLASSES.index(decision.canonical_class)


def _exclude(
    exclusions: list[ExclusionEvent],
    *,
    source_id: str,
    image_id: str,
    annotation_id: str | None,
    source_class: str | None,
    decision: MappingDecision,
) -> None:
    exclusions.append(
        ExclusionEvent(
            source_id=source_id,
            image_id=image_id,
            annotation_id=annotation_id,
            source_class=source_class,
            action=(
                "hold_for_review"
                if decision.action in {"keep", "safe_merge"}
                and decision.review_status != "approved"
                else decision.action
            ),
            reason=decision.reason,
        )
    )


def _hold_small_box(
    exclusions: list[ExclusionEvent],
    *,
    source_id: str,
    image_id: str,
    annotation_id: str,
    source_class: str,
    reason: str,
) -> None:
    exclusions.append(
        ExclusionEvent(
            source_id=source_id,
            image_id=image_id,
            annotation_id=annotation_id,
            source_class=source_class,
            action="hold_for_review",
            reason=reason,
        )
    )


def adapt_taco_coco(
    annotation_file: str | Path,
    *,
    mapping_table: MappingTable,
    source_id: str = "taco-v1.0",
    source_version: str = "v1.0",
) -> AdaptationResult:
    """Convert TACO COCO records without modifying the source annotation file."""

    with Path(annotation_file).open("r", encoding="utf-8") as handle:
        document = json.load(handle)

    categories = {int(item["id"]): str(item["name"]) for item in document["categories"]}
    image_records = {int(item["id"]): item for item in document["images"]}
    annotations_by_image: dict[int, list[CanonicalAnnotation]] = defaultdict(list)
    exclusions: list[ExclusionEvent] = []

    for raw in document["annotations"]:
        image_id = int(raw["image_id"])
        source_class = categories[int(raw["category_id"])]
        decision = mapping_table.resolve(source_id, source_class)
        annotation_id = str(raw["id"])
        if not decision.include_automatically:
            _exclude(
                exclusions,
                source_id=source_id,
                image_id=str(image_id),
                annotation_id=annotation_id,
                source_class=source_class,
                decision=decision,
            )
            continue

        image = image_records[image_id]
        width = int(image["width"])
        height = int(image["height"])
        x, y, box_width, box_height = (float(value) for value in raw["bbox"])
        box = NormalizedBox(
            xmin=x / width,
            ymin=y / height,
            xmax=(x + box_width) / width,
            ymax=(y + box_height) / height,
        )
        class_name = str(decision.canonical_class)
        size_reason = minimum_size_review_reason(
            box,
            class_name=class_name,
            image_width=width,
            image_height=height,
        )
        if size_reason is not None:
            _hold_small_box(
                exclusions,
                source_id=source_id,
                image_id=str(image_id),
                annotation_id=annotation_id,
                source_class=source_class,
                reason=size_reason,
            )
            continue
        annotations_by_image[image_id].append(
            CanonicalAnnotation(
                annotation_id=annotation_id,
                source_class=source_class,
                class_id=_mapped_class_id(decision),
                class_name=class_name,
                box=box,
            )
        )

    images: list[CanonicalImage] = []
    for image_id in sorted(annotations_by_image):
        raw = image_records[image_id]
        images.append(
            CanonicalImage(
                image_id=f"{source_id}:{image_id}",
                source_id=source_id,
                source_version=source_version,
                relative_path=safe_relative_path(str(raw["file_name"])),
                width=int(raw["width"]),
                height=int(raw["height"]),
                group_id=f"{source_id}:{image_id}",
                annotations=tuple(annotations_by_image[image_id]),
            )
        )
    return AdaptationResult(tuple(images), tuple(exclusions))


def adapt_open_images_csv(
    boxes_file: str | Path,
    class_descriptions_file: str | Path,
    image_manifest_file: str | Path,
    *,
    mapping_table: MappingTable,
    source_id: str = "open-images-v7-waste-subset",
    source_version: str = "V7",
) -> AdaptationResult:
    """Convert a manually selected Open Images subset with attribution metadata."""

    with Path(class_descriptions_file).open("r", encoding="utf-8", newline="") as handle:
        class_names = {row[0]: row[1] for row in csv.reader(handle) if len(row) >= 2}

    metadata: dict[str, dict[str, str]] = {}
    with Path(image_manifest_file).open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            metadata[row["ImageID"]] = row

    annotations_by_image: dict[str, list[CanonicalAnnotation]] = defaultdict(list)
    exclusions: list[ExclusionEvent] = []
    with Path(boxes_file).open("r", encoding="utf-8", newline="") as handle:
        for row_number, row in enumerate(csv.DictReader(handle), start=2):
            image_id = row["ImageID"]
            source_class = class_names[row["LabelName"]]
            decision = mapping_table.resolve(source_id, source_class)
            annotation_id = f"row-{row_number}"
            if not decision.include_automatically:
                _exclude(
                    exclusions,
                    source_id=source_id,
                    image_id=image_id,
                    annotation_id=annotation_id,
                    source_class=source_class,
                    decision=decision,
                )
                continue
            if image_id not in metadata:
                raise ValueError(f"Open Images metadata missing for ImageID {image_id}")
            image_metadata = metadata[image_id]
            box = NormalizedBox(
                xmin=float(row["XMin"]),
                ymin=float(row["YMin"]),
                xmax=float(row["XMax"]),
                ymax=float(row["YMax"]),
            )
            class_name = str(decision.canonical_class)
            size_reason = minimum_size_review_reason(
                box,
                class_name=class_name,
                image_width=int(image_metadata["Width"]),
                image_height=int(image_metadata["Height"]),
            )
            if size_reason is not None:
                _hold_small_box(
                    exclusions,
                    source_id=source_id,
                    image_id=image_id,
                    annotation_id=annotation_id,
                    source_class=source_class,
                    reason=size_reason,
                )
                continue
            annotations_by_image[image_id].append(
                CanonicalAnnotation(
                    annotation_id=annotation_id,
                    source_class=source_class,
                    class_id=_mapped_class_id(decision),
                    class_name=class_name,
                    box=box,
                )
            )

    images: list[CanonicalImage] = []
    for image_id in sorted(annotations_by_image):
        row = metadata[image_id]
        license_url = row.get("License", "").strip()
        author = row.get("Author", "").strip()
        if not license_url.startswith("https://creativecommons.org/licenses/by/2.0"):
            raise ValueError(f"unapproved or missing image license for ImageID {image_id}")
        if not author:
            raise ValueError(f"missing image author for ImageID {image_id}")
        images.append(
            CanonicalImage(
                image_id=f"{source_id}:{image_id}",
                source_id=source_id,
                source_version=source_version,
                relative_path=safe_relative_path(row["RelativePath"]),
                width=int(row["Width"]),
                height=int(row["Height"]),
                group_id=row.get("GroupID", "").strip() or f"{source_id}:{image_id}",
                annotations=tuple(annotations_by_image[image_id]),
                exact_hash=row.get("SHA256", "").strip() or None,
                attribution={
                    "author": author,
                    "license": license_url,
                    "landing_url": row.get("OriginalLandingURL", "").strip(),
                },
            )
        )
    return AdaptationResult(tuple(images), tuple(exclusions))
