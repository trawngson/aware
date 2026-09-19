"""Compare a Core ML export against its PyTorch reference (macOS only).

Core ML packages run only on Apple platforms, so this is the one model step
that runs on the Mac. It checks that every local image is byte-identical to
the image the server used, runs the package with the same Ultralytics
preprocessing, and applies ``compare_with_confidence_band``.

Usage (from backend/):
  python -m scripts.parity_coreml --reference REF.json --package X.mlpackage --images DIR
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

from src.canonical_data import NormalizedBox
from src.dedup import sha256_file
from src.parity import (
    Prediction,
    compare_with_confidence_band,
    predictions_from_json,
    predictions_to_json,
    validate_exported_labels,
)
from scripts.parity_reference import PREDICT_SETTINGS


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", required=True)
    parser.add_argument("--package", required=True)
    parser.add_argument("--images", required=True, help="folder searched recursively by file name")
    args = parser.parse_args()
    if platform.system() != "Darwin":
        raise SystemExit("Core ML packages can only run on macOS")

    reference_path = Path(args.reference)
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    local = {p.name: p for p in Path(args.images).rglob("*") if p.is_file()}
    missing = sorted(set(reference["image_sha256"]) - set(local))
    if missing:
        raise SystemExit(f"{len(missing)} reference images not found locally, e.g. {missing[:3]}")
    changed = [n for n, h in reference["image_sha256"].items() if sha256_file(local[n]) != h]
    if changed:
        raise SystemExit(f"{len(changed)} local images differ from the server copies, e.g. {changed[:3]}")
    print(f"{len(local)} local files scanned; all {len(reference['image_sha256'])} reference images match by SHA-256")

    from ultralytics import YOLO

    model = YOLO(args.package, task="detect")
    label_issues = validate_exported_labels([model.names[i] for i in sorted(model.names)])
    if label_issues:
        raise SystemExit("; ".join(label_issues))

    coreml: dict[str, list[Prediction]] = {}
    names = sorted(reference["image_sha256"])
    for index, name in enumerate(names, start=1):
        result = model.predict(source=str(local[name]), device="cpu", **PREDICT_SETTINGS)[0]
        boxes = result.boxes
        coreml[name] = [
            Prediction(int(c), float(p), NormalizedBox(*map(float, xyxy)))
            for c, p, xyxy in zip(boxes.cls.tolist(), boxes.conf.tolist(), boxes.xyxyn.tolist())
        ]
        if index % 25 == 0:
            print(f"  predicted {index}/{len(names)}", flush=True)

    report = compare_with_confidence_band(predictions_from_json(reference["predictions"]), coreml)
    print(report.render())
    result_path = reference_path.with_name("parity_result.json")
    result_path.write_text(
        json.dumps(
            {
                "model_version": reference["model_version"],
                "checkpoint_sha256": reference["checkpoint_sha256"],
                "package": Path(args.package).name,
                "ok": report.ok,
                "issues": [issue.__dict__ for issue in report.issues],
                "coreml_predictions": predictions_to_json(coreml),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {result_path}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
