"""Immutable canonical dataset release writing."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, replace
from pathlib import Path
from typing import Mapping, Sequence

import yaml

from .audit import DatasetAuditReport
from .canonical_data import CanonicalImage, ExclusionEvent, image_to_dict
from .dedup import difference_hash, perceptual_duplicate_groups, sha256_file
from .image_files import TRANSPOSE_ORIENTATIONS, materialize_exif_oriented_copy
from .metadata_validation import EXPECTED_CLASSES
from .splitting import LeakageViolation


def attach_image_hashes(
    images: Sequence[CanonicalImage],
    source_roots: Mapping[str, Path],
) -> tuple[CanonicalImage, ...]:
    hashed: list[CanonicalImage] = []
    for image in images:
        image_path = source_roots[image.source_id] / image.relative_path
        hashed.append(
            replace(
                image,
                exact_hash=sha256_file(image_path),
                perceptual_hash=difference_hash(image_path),
            )
        )
    return tuple(hashed)


def perceptual_groups_for_images(
    images: Sequence[CanonicalImage],
    *,
    maximum_distance: int = 5,
) -> dict[str, str]:
    hashes = {
        image.image_id: image.perceptual_hash
        for image in images
        if image.perceptual_hash is not None
    }
    return perceptual_duplicate_groups(hashes, maximum_distance=maximum_distance)


def _release_filename(image: CanonicalImage) -> str:
    import hashlib

    suffix = Path(image.relative_path).suffix.lower() or ".img"
    digest = hashlib.sha256(image.image_id.encode("utf-8")).hexdigest()[:20]
    return f"{digest}{suffix}"


def write_yolo_release(
    images: Sequence[CanonicalImage],
    assignments: Mapping[str, str],
    source_roots: Mapping[str, Path],
    destination: str | Path,
    *,
    release_id: str,
    seed: int,
    audit_report: DatasetAuditReport,
    duplicate_groups: Mapping[str, str],
    leakage_violations: Sequence[LeakageViolation],
    exclusions: Sequence[ExclusionEvent] = (),
) -> Path:
    """Write one new release without modifying immutable raw images."""

    output = Path(destination)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite dataset release: {output}")
    if not audit_report.ok:
        raise ValueError("cannot release a dataset whose audit has errors")
    if leakage_violations:
        raise ValueError("cannot release a dataset with cross-split leakage")
    if set(assignments) != {image.image_id for image in images}:
        raise ValueError("split assignments must exactly cover canonical images")

    output.mkdir(parents=True, exist_ok=False)
    manifests = output / "manifests"
    manifests.mkdir()
    split_names = sorted(set(assignments.values()))
    for split in split_names:
        (output / "images" / split).mkdir(parents=True)
        (output / "labels" / split).mkdir(parents=True)

    release_images: list[dict[str, object]] = []
    for image in sorted(images, key=lambda item: item.image_id):
        split = assignments[image.image_id]
        filename = _release_filename(image)
        source_path = (source_roots[image.source_id] / image.relative_path).resolve()
        image_link = output / "images" / split / filename
        source_orientation = materialize_exif_oriented_copy(
            source_path,
            image_link,
            expected_size=(image.width, image.height),
        )
        if source_orientation not in TRANSPOSE_ORIENTATIONS:
            os.symlink(source_path, image_link)
            release_image = {
                "mode": "raw_symlink",
                "exif_transposed": False,
                "source_exif_orientation": source_orientation,
            }
        else:
            release_image = {
                "mode": "derived_copy",
                "exif_transposed": True,
                "source_exif_orientation": source_orientation,
            }
        label_path = output / "labels" / split / f"{Path(filename).stem}.txt"
        with label_path.open("x", encoding="utf-8") as handle:
            for annotation in image.annotations:
                x_center, y_center, width, height = annotation.box.as_yolo()
                handle.write(
                    f"{annotation.class_id} {x_center:.8f} {y_center:.8f} "
                    f"{width:.8f} {height:.8f}\n"
                )
        record = image_to_dict(image)
        record["split"] = split
        record["release_filename"] = filename
        record["release_image"] = release_image
        record["duplicate_group"] = duplicate_groups.get(image.image_id)
        release_images.append(record)

    dataset_yaml = {
        "path": str(output.resolve()),
        **{split: f"images/{split}" for split in split_names},
        "names": {index: name for index, name in enumerate(EXPECTED_CLASSES)},
    }
    with (output / "dataset.yaml").open("x", encoding="utf-8") as handle:
        yaml.safe_dump(dataset_yaml, handle, sort_keys=False)
    with (manifests / "canonical_images.jsonl").open("x", encoding="utf-8") as handle:
        for record in release_images:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    split_manifest = {
        "schema_version": "1.0",
        "split_version": release_id,
        "seed": seed,
        "assignments": dict(sorted(assignments.items())),
        "perceptual_duplicate_groups": dict(sorted(duplicate_groups.items())),
        "leakage_violations": [asdict(item) for item in leakage_violations],
    }
    (manifests / "split_manifest.json").write_text(
        json.dumps(split_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    audit_document = {
        "ok": audit_report.ok,
        "image_counts_by_source": audit_report.image_counts_by_source,
        "annotation_counts_by_class": audit_report.annotation_counts_by_class,
        "findings": [asdict(item) for item in audit_report.findings],
    }
    (manifests / "audit_report.json").write_text(
        json.dumps(audit_document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (manifests / "exclusions.jsonl").open("x", encoding="utf-8") as handle:
        for exclusion in exclusions:
            handle.write(json.dumps(asdict(exclusion), sort_keys=True) + "\n")
    return output
