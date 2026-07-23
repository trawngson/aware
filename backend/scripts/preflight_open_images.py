"""Download official validation metadata and prepare Open Images class review."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import urllib.request
from pathlib import Path

from src.open_images_preflight import build_open_images_preflight
from src.project_paths import ProjectPaths, require_path_within


OFFICIAL_URLS = {
    "class_descriptions": (
        "https://storage.googleapis.com/openimages/v7/"
        "oidv7-class-descriptions-boxable.csv"
    ),
    "boxes": (
        "https://storage.googleapis.com/openimages/v5/"
        "validation-annotations-bbox.csv"
    ),
    "image_metadata": (
        "https://storage.googleapis.com/openimages/2018_04/validation/"
        "validation-images-with-rotation.csv"
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Metadata-only Open Images validation preflight; downloads no images"
        )
    )
    parser.add_argument(
        "--destination",
        default="raw/open-images/v7-waste-subset/preflight-validation-v1",
        help="new directory relative to PROJECT_DATA_ROOT",
    )
    parser.add_argument("--sample-per-class", type=int, default=48)
    parser.add_argument("--seed", type=int, default=26)
    return parser.parse_args()


def download(url: str, destination: Path) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "AWARE-open-images-preflight/1.0"},
    )
    digest = hashlib.sha256()
    received = 0
    with urllib.request.urlopen(request, timeout=60) as response:
        expected = int(response.headers.get("Content-Length", "0"))
        print(
            f"Downloading metadata: {destination.name} "
            f"({expected / (1024**2):.1f} MiB reported)"
        )
        with destination.open("xb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                digest.update(chunk)
                received += len(chunk)
    if expected and received != expected:
        raise RuntimeError(
            f"incomplete download for {destination.name}: "
            f"{received} of {expected} bytes"
        )
    print(f"Downloaded {destination.name}: {received / (1024**2):.1f} MiB")
    return digest.hexdigest()


def main() -> int:
    args = parse_args()
    paths = ProjectPaths.from_environment()
    paths.assert_expected_working_directory()

    destination = require_path_within(
        args.destination,
        paths.data_root,
        must_exist=False,
    )
    if destination.exists():
        raise FileExistsError(
            f"refusing to overwrite existing preflight: {destination}"
        )

    staging = destination.with_name(
        f".{destination.name}.part-{os.getpid()}"
    )
    require_path_within(staging, paths.data_root, must_exist=False)
    staging.mkdir(parents=True, exist_ok=False)
    official = staging / "official"
    official.mkdir()

    source_hashes = {}
    files = {
        "class_descriptions": official / "class-descriptions-boxable.csv",
        "boxes": official / "validation-annotations-bbox.csv",
        "image_metadata": official / "validation-images-with-rotation.csv",
    }
    try:
        for name, url in OFFICIAL_URLS.items():
            source_hashes[name] = download(url, files[name])

        report = build_open_images_preflight(
            class_descriptions_file=files["class_descriptions"],
            boxes_file=files["boxes"],
            image_metadata_file=files["image_metadata"],
            destination=staging / "filtered",
            split="validation",
            sample_per_class=args.sample_per_class,
            seed=args.seed,
            source_urls=OFFICIAL_URLS,
        )

        with (staging / "source-sha256.txt").open(
            "x", encoding="utf-8"
        ) as handle:
            for name in sorted(source_hashes):
                handle.write(f"{source_hashes[name]}  {files[name].name}\n")

        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, destination)
    except Exception:
        print(
            f"Preflight stopped. Partial evidence preserved at: {staging}",
            file=sys.stderr,
        )
        raise

    print("OPEN_IMAGES_PREFLIGHT_PASS")
    print("candidate class MIDs:", report["candidate_class_mids"])
    print("box counts:", report["box_counts"])
    print("selected images:", report["selected_image_count"])
    print("review images:", report["review_image_count"])
    print("review rows by class:", report["review_rows_by_class"])
    print("rejected review attributes:", report["rejected_review_attributes"])
    print("license counts:", report["attribution"]["license_counts"])
    print("missing authors:", report["attribution"]["missing_author_count"])
    print(
        "estimated full selected-image GiB:",
        report["estimated_original_image_gib"],
    )
    print("No images were downloaded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
