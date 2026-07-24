"""Build the approved Open Images train selection from official metadata."""

from __future__ import annotations

import argparse
import os
import shutil
import sys

from src.open_images_training_selection import (
    select_open_images_training_metadata,
)
from src.project_paths import ProjectPaths, require_path_within


SOURCE_URLS = {
    "class_descriptions": (
        "https://storage.googleapis.com/openimages/v7/"
        "oidv7-class-descriptions-boxable.csv"
    ),
    "boxes": (
        "https://storage.googleapis.com/openimages/v6/"
        "oidv6-train-annotations-bbox.csv"
    ),
    "image_metadata": (
        "https://storage.googleapis.com/openimages/2018_04/train/"
        "train-images-boxable-with-rotation.csv"
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--class-descriptions", required=True)
    parser.add_argument("--boxes", required=True)
    parser.add_argument("--image-metadata", required=True)
    parser.add_argument(
        "--destination",
        default="raw/open-images/v7-waste-subset/train-selection-v1",
    )
    parser.add_argument(
        "--visible-report",
        default="reports/open-images-train-selection-v1.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = ProjectPaths.from_environment()
    paths.assert_expected_working_directory()

    class_descriptions = require_path_within(
        args.class_descriptions, paths.data_root
    )
    boxes = require_path_within(args.boxes, paths.data_root)
    image_metadata = require_path_within(
        args.image_metadata, paths.data_root
    )
    destination = require_path_within(
        args.destination, paths.data_root, must_exist=False
    )
    visible_report = require_path_within(
        args.visible_report, paths.output_root, must_exist=False
    )
    if destination.exists():
        raise FileExistsError(f"selection already exists: {destination}")
    if visible_report.exists():
        raise FileExistsError(f"visible report already exists: {visible_report}")

    staging = destination.with_name(f".{destination.name}.part-{os.getpid()}")
    require_path_within(staging, paths.data_root, must_exist=False)
    try:
        report = select_open_images_training_metadata(
            class_descriptions_file=class_descriptions,
            boxes_file=boxes,
            image_metadata_file=image_metadata,
            destination=staging,
            source_urls=SOURCE_URLS,
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, destination)
        visible_report.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(destination / "selection-report.json", visible_report)
    except Exception:
        print(
            f"Selection stopped; partial evidence preserved at {staging}",
            file=sys.stderr,
        )
        raise

    print("OPEN_IMAGES_TRAIN_SELECTION_PASS")
    print("box counts:", report["selected_box_counts"])
    print(
        "image counts by class:",
        report["selected_image_counts_by_class"],
    )
    print("unique images:", report["selected_unique_image_count"])
    print("excluded attributes:", report["excluded_attribute_counts"])
    print("invalid boxes:", report["invalid_box_counts"])
    print("license counts:", report["attribution"]["license_counts"])
    print(
        "attribution rejections:",
        report["attribution"]["rejected_counts"],
    )
    print("estimated original GiB:", report["estimated_original_gib"])
    print("visible report:", visible_report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
