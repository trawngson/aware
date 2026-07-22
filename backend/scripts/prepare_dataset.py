"""Build a new canonical YOLO dataset release on VAST.

This is never run automatically. Review its arguments in the remote notebook,
run the read-only inventory first, and point every input inside
PROJECT_DATA_ROOT. Raw inputs are read-only. The new release is written only
under PROJECT_OUTPUT_ROOT/datasets and existing releases are never overwritten.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from src.adapters import adapt_open_images_csv, adapt_taco_coco
from src.audit import audit_canonical_images
from src.metadata_validation import EXPECTED_CLASSES, load_yaml_mapping
from src.mappings import MappingTable
from src.project_paths import ProjectPaths, require_path_within
from src.release import attach_image_hashes, perceptual_groups_for_images, write_yolo_release
from src.splitting import assign_group_aware_splits, find_leakage


RELEASE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--taco-annotations", required=True)
    parser.add_argument("--taco-images", required=True)
    parser.add_argument("--open-images-boxes", required=True)
    parser.add_argument("--open-images-classes", required=True)
    parser.add_argument("--open-images-manifest", required=True)
    parser.add_argument("--open-images-images", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not RELEASE_PATTERN.fullmatch(args.release_id):
        raise ValueError("release ID must use lowercase letters, digits, dot, dash, or underscore")
    if args.seed < 0:
        raise ValueError("seed must be non-negative")

    paths = ProjectPaths.from_environment()
    paths.assert_expected_working_directory()
    resolve_data = lambda value: require_path_within(value, paths.data_root)
    taco_annotations = resolve_data(args.taco_annotations)
    taco_images = resolve_data(args.taco_images)
    open_images_boxes = resolve_data(args.open_images_boxes)
    open_images_classes = resolve_data(args.open_images_classes)
    open_images_manifest = resolve_data(args.open_images_manifest)
    open_images_images = resolve_data(args.open_images_images)
    for directory in (taco_images, open_images_images):
        if not directory.is_dir():
            raise ValueError(f"image root is not a directory: {directory}")

    ledger = load_yaml_mapping(paths.project_root / "mapping_ledger.yaml")
    mapping_table = MappingTable.from_document(ledger)
    taco = adapt_taco_coco(taco_annotations, mapping_table=mapping_table)
    open_images = adapt_open_images_csv(
        open_images_boxes,
        open_images_classes,
        open_images_manifest,
        mapping_table=mapping_table,
    )
    images = taco.images + open_images.images
    roots = {
        "taco-v1.0": taco_images,
        "open-images-v7-waste-subset": open_images_images,
    }

    audit = audit_canonical_images(
        images,
        source_roots=roots,
        required_classes=EXPECTED_CLASSES,
        verify_image_files=True,
    )
    print(audit.render())
    print(f"exclusions: TACO={len(taco.exclusions)} OpenImages={len(open_images.exclusions)}")
    if not audit.ok:
        return 2

    hashed_images = attach_image_hashes(images, roots)
    duplicate_groups = perceptual_groups_for_images(hashed_images)
    assignments = assign_group_aware_splits(
        hashed_images,
        seed=args.seed,
        duplicate_groups=duplicate_groups,
    )
    leakage = find_leakage(hashed_images, assignments, duplicate_groups=duplicate_groups)
    if leakage:
        for violation in leakage:
            print(violation)
        return 2

    destination = require_path_within(
        Path("datasets") / args.release_id,
        paths.output_root,
        must_exist=False,
    )
    write_yolo_release(
        hashed_images,
        assignments,
        roots,
        destination,
        release_id=args.release_id,
        seed=args.seed,
        audit_report=audit,
        duplicate_groups=duplicate_groups,
        leakage_violations=leakage,
        exclusions=taco.exclusions + open_images.exclusions,
    )
    print(f"release created: {destination}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
