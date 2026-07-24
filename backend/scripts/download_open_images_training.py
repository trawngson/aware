"""Acquire the approved Open Images training pixels from the official mirror."""

from __future__ import annotations

import argparse
import shutil

from src.open_images_acquisition import acquire_open_images_training_images
from src.project_paths import ProjectPaths, require_path_within


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--selection",
        default="raw/open-images/v7-waste-subset/train-selection-v1",
    )
    parser.add_argument(
        "--destination",
        default="raw/open-images/v7-waste-subset/train-images-v1",
    )
    parser.add_argument(
        "--visible-report",
        default="reports/open-images-train-acquisition-v1.json",
    )
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--timeout-seconds", type=float, default=60)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = ProjectPaths.from_environment()
    paths.assert_expected_working_directory()

    selection = require_path_within(args.selection, paths.data_root)
    destination = require_path_within(
        args.destination, paths.data_root, must_exist=False
    )
    visible_report = require_path_within(
        args.visible_report, paths.output_root, must_exist=False
    )
    if not selection.is_dir():
        raise ValueError(f"selection is not a directory: {selection}")
    if visible_report.exists():
        raise FileExistsError(
            f"visible acquisition report already exists: {visible_report}"
        )

    report = acquire_open_images_training_images(
        selection_directory=selection,
        destination=destination,
        workers=args.workers,
        retries=args.retries,
        timeout_seconds=args.timeout_seconds,
    )

    visible_report.parent.mkdir(parents=True, exist_ok=True)
    with (destination / "acquisition-report.json").open("rb") as source:
        with visible_report.open("xb") as target:
            shutil.copyfileobj(source, target)

    print("OPEN_IMAGES_TRAIN_ACQUISITION_PASS")
    print("verified images:", report["verified_image_count"])
    print("status counts:", report["status_counts"])
    print("actual mirror GiB:", report["actual_mirror_gib"])
    print("license counts:", report["attribution"]["license_counts"])
    print("decode failures:", report["image_decode"]["failure_count"])
    print("visible report:", visible_report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
