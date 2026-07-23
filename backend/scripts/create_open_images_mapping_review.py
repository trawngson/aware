"""Create bounded Open Images mapping-review sheets from approved preflight."""

from __future__ import annotations

import argparse
import os
import sys

from src.open_images_review import create_open_images_review
from src.project_paths import ProjectPaths, require_path_within


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--preflight",
        default="raw/open-images/v7-waste-subset/preflight-validation-v1",
        help="preflight directory relative to PROJECT_DATA_ROOT",
    )
    parser.add_argument(
        "--destination",
        default="reviews/open-images-validation-seed26-v1",
        help="new review directory relative to PROJECT_OUTPUT_ROOT",
    )
    parser.add_argument("--workers", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = ProjectPaths.from_environment()
    paths.assert_expected_working_directory()
    preflight = require_path_within(args.preflight, paths.data_root)
    destination = require_path_within(
        args.destination,
        paths.output_root,
        must_exist=False,
    )
    if destination.exists():
        raise FileExistsError(
            f"refusing to overwrite existing review: {destination}"
        )

    staging = destination.with_name(f".{destination.name}.part-{os.getpid()}")
    require_path_within(staging, paths.output_root, must_exist=False)
    try:
        report = create_open_images_review(
            preflight_directory=preflight,
            destination=staging,
            workers=args.workers,
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, destination)
    except Exception:
        print(
            f"Review stopped. Partial evidence preserved at: {staging}",
            file=sys.stderr,
        )
        raise
    print("OPEN_IMAGES_REVIEW_PASS")
    print("review rows:", report["review_rows"])
    print("unique images:", report["unique_images"])
    print("download MiB:", round(report["download_bytes"] / (1024**2), 1))
    print("review sheets:", len(report["sheets"]))
    print(
        "download this file:",
        destination / report["complete_review"]["path"],
    )
    print(
        "complete review sha256:",
        report["complete_review"]["sha256"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
