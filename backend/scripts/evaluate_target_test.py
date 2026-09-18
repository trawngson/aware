"""Evaluate one trained checkpoint once on the frozen smartphone test set (VAST only).

The manifest and every pinned image are verified before any model runs. Each
(checkpoint, manifest) pair may be evaluated only once: a second attempt is
refused so test-set results cannot be re-rolled.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

from src.dedup import sha256_file
from src.metadata_validation import EXPECTED_CLASSES
from src.project_paths import ProjectPaths, require_path_within
from src.target_evaluation import (
    APP_AUTO_CONFIRM_THRESHOLD,
    TOP1_HEADLINE_THRESHOLD,
    TOP1_THRESHOLDS,
    build_eval_dataset,
    load_verified_manifest,
    score_top1,
)
from src.validation import validate_environment

EVAL_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
VAL_SETTINGS = {"imgsz": 640, "batch": 16, "conf": 0.001, "iou": 0.7, "split": "val"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", required=True, help="best.pt under PROJECT_OUTPUT_ROOT/runs")
    parser.add_argument("--manifest", required=True, help="frozen manifest under the code root")
    parser.add_argument("--test-root", required=True, help="unpacked test images under PROJECT_DATA_ROOT")
    parser.add_argument("--eval-id", required=True)
    return parser.parse_args()


def _prior_evaluation(evaluations: Path, weights_sha256: str, manifest_checksum: str) -> Path | None:
    for record_path in sorted(evaluations.glob("*.json")):
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (
            record.get("weights_sha256") == weights_sha256
            and record.get("manifest_checksum") == manifest_checksum
        ):
            return record_path
    return None


def _write(path: Path, record: dict[str, Any]) -> None:
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    if not EVAL_PATTERN.fullmatch(args.eval_id):
        raise ValueError("eval ID must use lowercase letters, digits, dot, dash, or underscore")

    paths = ProjectPaths.from_environment()
    paths.assert_expected_working_directory()
    preflight = validate_environment(paths, require_data=True, require_output=True)
    print(preflight.render())
    if not preflight.ok:
        return 2

    weights = require_path_within(args.weights, paths.output_root)
    if not weights.is_file() or weights.suffix != ".pt":
        raise ValueError("weights must be an existing .pt checkpoint under PROJECT_OUTPUT_ROOT")
    manifest_path = require_path_within(args.manifest, paths.project_root)
    test_root = require_path_within(args.test_root, paths.data_root)

    print("verifying frozen manifest and every pinned image ...", flush=True)
    manifest = load_verified_manifest(manifest_path, test_root=test_root)
    checksum = str(manifest["manifest_checksum"])
    print(f"manifest {manifest['manifest_id']} verified: {len(manifest['images'])} images")

    evaluations = require_path_within("evaluations", paths.output_root, must_exist=False)
    evaluations.mkdir(parents=True, exist_ok=True)
    record_path = evaluations / f"{args.eval_id}.json"
    if record_path.exists():
        raise FileExistsError(f"refusing to overwrite evaluation record: {record_path}")
    weights_sha256 = sha256_file(weights)
    prior = _prior_evaluation(evaluations, weights_sha256, checksum)
    if prior is not None:
        raise FileExistsError(f"this checkpoint was already evaluated on this test set: {prior}")

    dataset_yaml = build_eval_dataset(
        manifest,
        test_root=test_root,
        destination=require_path_within(
            Path("eval_datasets") / str(manifest["manifest_id"]), paths.output_root, must_exist=False
        ),
    )

    record: dict[str, Any] = {
        "schema_version": "1.0",
        "eval_id": args.eval_id,
        "status": "running",
        "weights": str(weights.relative_to(paths.output_root)),
        "weights_sha256": weights_sha256,
        "manifest_id": manifest["manifest_id"],
        "manifest_checksum": checksum,
        "test_images": len(manifest["images"]),
        "test_boxes": manifest["counts"]["boxes"],
        "val_settings": VAL_SETTINGS,
        "top1_headline_threshold": TOP1_HEADLINE_THRESHOLD,
        "app_auto_confirm_threshold": APP_AUTO_CONFIRM_THRESHOLD,
    }
    _write(record_path, record)

    from ultralytics import YOLO
    import torch

    model = YOLO(str(weights))
    names = tuple(model.names[index] for index in sorted(model.names))
    if names != EXPECTED_CLASSES:
        record["status"] = "failed"
        record["failure"] = f"checkpoint class order mismatch: {names}"
        _write(record_path, record)
        raise ValueError(record["failure"])
    record["environment"] = {
        "python_version": sys.version.split()[0],
        "ultralytics_version": __import__("ultralytics").__version__,
        "torch_version": torch.__version__,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    }

    started = time.monotonic()
    try:
        metrics = model.val(
            data=str(dataset_yaml),
            device=0,
            project=str(evaluations),
            name=args.eval_id,
            exist_ok=False,
            plots=True,
            **VAL_SETTINGS,
        )
        box = metrics.box
        per_class = []
        for index, class_id in enumerate(box.ap_class_index):
            precision, recall, ap50, ap50_95 = box.class_result(index)
            per_class.append(
                {
                    "class": EXPECTED_CLASSES[int(class_id)],
                    "precision": round(float(precision), 4),
                    "recall": round(float(recall), 4),
                    "map50": round(float(ap50), 4),
                    "map50_95": round(float(ap50_95), 4),
                }
            )
        record["overall"] = {
            "precision": round(float(box.mp), 4),
            "recall": round(float(box.mr), 4),
            "map50": round(float(box.map50), 4),
            "map50_95": round(float(box.map), 4),
        }
        record["per_class"] = per_class

        predictions: dict[str, list[tuple[int, float]]] = {}
        images_dir = dataset_yaml.parent / "images"
        for result in model.predict(
            source=str(images_dir), imgsz=640, conf=0.001, device=0, stream=True, verbose=False
        ):
            classes = result.boxes.cls.tolist() if result.boxes is not None else []
            confidences = result.boxes.conf.tolist() if result.boxes is not None else []
            predictions[Path(result.path).name] = [
                (int(c), float(p)) for c, p in zip(classes, confidences)
            ]
        record["top1"] = [
            outcome.as_dict() for outcome in score_top1(manifest, predictions, thresholds=TOP1_THRESHOLDS)
        ]
    except Exception as error:
        record["status"] = "failed"
        record["failure"] = f"{type(error).__name__}: {error}"
        record["duration_seconds"] = round(time.monotonic() - started, 3)
        _write(record_path, record)
        raise

    record["status"] = "completed"
    record["duration_seconds"] = round(time.monotonic() - started, 3)
    _write(record_path, record)

    print(f"\n===== {args.eval_id}: frozen test set {manifest['manifest_id']} =====")
    overall = record["overall"]
    print(
        f"overall  P {overall['precision']:.3f}  R {overall['recall']:.3f}  "
        f"mAP50 {overall['map50']:.3f}  mAP50-95 {overall['map50_95']:.3f}"
    )
    for row in per_class:
        print(
            f"  {row['class']:16s} P {row['precision']:.3f}  R {row['recall']:.3f}  "
            f"mAP50 {row['map50']:.3f}  mAP50-95 {row['map50_95']:.3f}"
        )
    for outcome in record["top1"]:
        print(
            f"top-1 @ conf>={outcome['confidence_threshold']}: correct {outcome['correct']}"
            f"/{outcome['images']}  wrong {outcome['wrong']}  abstained {outcome['abstained']}"
        )
    print(f"record: {record_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
