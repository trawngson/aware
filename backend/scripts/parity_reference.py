"""Record PyTorch reference predictions for a Core ML export (VAST only).

Runs the exact checkpoint copied into an export folder on a fixed image set
and writes ``parity_reference.json`` beside the export. The Mac-side
``scripts/parity_coreml.py`` runs the exported package on the same images and
compares. Never overwrites an existing reference.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.dedup import sha256_file
from src.metadata_validation import EXPECTED_CLASSES
from src.parity import Prediction, predictions_to_json
from src.canonical_data import NormalizedBox
from src.project_paths import ProjectPaths, require_path_within

# Shared with parity_coreml.py: square 640 letterbox and a confidence floor
# below the 0.25 comparison threshold minus its 0.05 band.
PREDICT_SETTINGS = {"imgsz": 640, "conf": 0.2, "iou": 0.7, "rect": False, "verbose": False}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-dir", required=True, help="exports/<model-version> under PROJECT_OUTPUT_ROOT")
    parser.add_argument("--images", required=True, help="image folder under PROJECT_OUTPUT_ROOT")
    args = parser.parse_args()

    paths = ProjectPaths.from_environment()
    paths.assert_expected_working_directory()
    export_dir = require_path_within(args.export_dir, paths.output_root)
    images_dir = require_path_within(args.images, paths.output_root)
    checkpoint = export_dir / "selected.pt"
    output = export_dir / "parity_reference.json"
    if not checkpoint.is_file():
        raise FileNotFoundError(f"missing exported checkpoint copy: {checkpoint}")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    images = sorted(p for p in images_dir.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
    if not images:
        raise ValueError(f"no images in {images_dir}")

    from ultralytics import YOLO
    import torch

    model = YOLO(str(checkpoint))
    if tuple(model.names[i] for i in sorted(model.names)) != EXPECTED_CLASSES:
        raise ValueError("checkpoint class order does not match the ontology")
    device = 0 if torch.cuda.is_available() else "cpu"

    predictions: dict[str, list[Prediction]] = {}
    for index, result in enumerate(
        model.predict(source=str(images_dir), device=device, stream=True, **PREDICT_SETTINGS), start=1
    ):
        name = Path(result.path).name
        boxes = result.boxes
        predictions[name] = [
            Prediction(int(c), float(p), NormalizedBox(*map(float, xyxy)))
            for c, p, xyxy in zip(boxes.cls.tolist(), boxes.conf.tolist(), boxes.xyxyn.tolist())
        ]
        if index % 25 == 0:
            print(f"  predicted {index}/{len(images)}", flush=True)

    document = {
        "schema_version": "1.0",
        "model_version": export_dir.name,
        "checkpoint_sha256": sha256_file(checkpoint),
        "framework": "pytorch",
        "torch_version": torch.__version__,
        "ultralytics_version": __import__("ultralytics").__version__,
        "device": str(device),
        "predict_settings": PREDICT_SETTINGS,
        "image_sha256": {p.name: sha256_file(p) for p in images},
        "predictions": predictions_to_json(predictions),
    }
    with output.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(document, indent=2, sort_keys=True) + "\n")
    detections = sum(len(items) for items in predictions.values())
    print(f"wrote {output} ({len(predictions)} images, {detections} detections at conf >= 0.2)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
