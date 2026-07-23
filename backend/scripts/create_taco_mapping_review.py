"""Create deterministic contact sheets for proposed safe TACO mappings."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from src.mapping_review import (
    load_coco_document,
    render_review_sheets,
    select_review_samples,
)
from src.metadata_validation import load_yaml_mapping
from src.project_paths import ProjectPaths, require_path_within


REVIEW_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-id", required=True)
    parser.add_argument("--annotations", required=True)
    parser.add_argument("--images", required=True)
    parser.add_argument("--seed", type=int, default=26)
    parser.add_argument("--samples-per-class", type=int, default=12)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not REVIEW_ID_PATTERN.fullmatch(args.review_id):
        raise ValueError("review ID must use lowercase letters, digits, dot, dash, or underscore")

    paths = ProjectPaths.from_environment()
    paths.assert_expected_working_directory()
    annotation_file = require_path_within(args.annotations, paths.data_root)
    image_root = require_path_within(args.images, paths.data_root)
    destination = require_path_within(
        Path("reviews") / args.review_id,
        paths.output_root,
        must_exist=False,
    )
    if not image_root.is_dir():
        raise ValueError(f"image root is not a directory: {image_root}")

    ledger = load_yaml_mapping(paths.project_root / "mapping_ledger.yaml")
    safe_mappings = [
        entry
        for entry in ledger["mappings"]
        if entry["source"] == "taco-v1.0"
        and entry["action"] in {"keep", "safe_merge"}
        and entry["review_status"] == "representative_samples_required"
    ]
    safe_classes = [entry["source_class"] for entry in safe_mappings]
    target_classes = {
        entry["source_class"]: entry["canonical_class"] for entry in safe_mappings
    }
    document = load_coco_document(annotation_file)
    selected = select_review_samples(
        document,
        safe_classes,
        seed=args.seed,
        samples_per_class=args.samples_per_class,
    )
    empty = [name for name, samples in selected.items() if not samples]
    if empty:
        raise ValueError(f"safe mappings have no source annotations: {empty}")

    rendered = render_review_sheets(
        selected,
        image_root,
        destination,
        target_classes=target_classes,
        progress=lambda source_class, completed, total: print(
            f"rendered {completed}/{total}: {source_class}",
            flush=True,
        ),
    )
    print(f"review directory: {destination}")
    print(f"safe source classes: {len(rendered)}")
    print(f"selected annotations: {sum(len(items) for items in selected.values())}")
    print(f"index: {destination / 'index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
