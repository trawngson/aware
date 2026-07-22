"""Export one selected VAST checkpoint to a new FP16 Core ML release folder.

Run manually on VAST after model selection. This script refuses local defaults,
requires the checkpoint to live under PROJECT_OUTPUT_ROOT, and never overwrites
or deletes an existing export.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

from src.metadata_validation import EXPECTED_CLASSES
from src.project_paths import ProjectPaths, require_path_within


VERSION_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
MAXIMUM_PACKAGE_BYTES = 25 * 1024 * 1024


def package_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True, help="Path within PROJECT_OUTPUT_ROOT")
    parser.add_argument("--model-version", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not VERSION_PATTERN.fullmatch(args.model_version):
        raise ValueError("model version must use lowercase letters, digits, dot, dash, or underscore")

    paths = ProjectPaths.from_environment()
    paths.assert_expected_working_directory()
    checkpoint = require_path_within(args.checkpoint, paths.output_root)
    if not checkpoint.is_file() or checkpoint.suffix != ".pt":
        raise ValueError("checkpoint must be an existing .pt file under PROJECT_OUTPUT_ROOT")

    export_directory = require_path_within(
        Path("exports") / args.model_version,
        paths.output_root,
        must_exist=False,
    )
    export_directory.mkdir(parents=True, exist_ok=False)
    staged_checkpoint = export_directory / "selected.pt"
    shutil.copy2(checkpoint, staged_checkpoint)

    from ultralytics import YOLO

    model = YOLO(str(staged_checkpoint))
    labels = tuple(model.names[index] for index in sorted(model.names))
    if labels != EXPECTED_CLASSES:
        raise RuntimeError(f"checkpoint label order mismatch: {labels}")

    exported = Path(
        model.export(
            format="coreml",
            imgsz=640,
            quantize=16,
            nms=False,
            batch=1,
        )
    )
    if not exported.is_dir() or exported.suffix != ".mlpackage":
        raise RuntimeError(f"unexpected Core ML export result: {exported}")
    size = package_size(exported)
    record = {
        "model_version": args.model_version,
        "format": "Core ML package",
        "precision": "FP16",
        "image_size": 640,
        "nms": "YOLO26 end-to-end; embedded NMS disabled",
        "labels": list(labels),
        "package_path": exported.name,
        "package_bytes": size,
        "package_limit_bytes": MAXIMUM_PACKAGE_BYTES,
        "package_size_pass": size <= MAXIMUM_PACKAGE_BYTES,
        "parity_status": "pending",
    }
    record_path = export_directory / "export_record.json"
    record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))
    return 0 if record["package_size_pass"] else 2


if __name__ == "__main__":
    sys.exit(main())
