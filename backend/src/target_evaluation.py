"""Evaluate trained detectors once on the frozen smartphone target test set.

The frozen manifest (see :mod:`src.target_test_set`) pins every test image by
SHA-256 and stores its boxes in canonical ontology order. This module turns a
verified manifest into a YOLO evaluation directory and scores per-image
predictions with a "top-1 correct" rule that mirrors how the app uses the
detector: it acts on the single most confident detection.

Everything here is pure Python so it can be tested locally. Running a model
belongs to ``scripts/evaluate_target_test.py`` on VAST.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml

from .metadata_validation import EXPECTED_CLASSES
from .target_test_set import TargetTestSetError, verify_frozen_test_manifest

EVAL_DATASET_MARKER = "eval_dataset_source.json"

# Pre-registered on 2026-09-19, before any test-set evaluation. 0.25 is the
# Ultralytics prediction default; 0.75 is the app's auto-confirm threshold
# (awareapp/Views/Scan/ScanTabView.swift autoConfirmThreshold).
TOP1_HEADLINE_THRESHOLD = 0.25
APP_AUTO_CONFIRM_THRESHOLD = 0.75
TOP1_THRESHOLDS = (TOP1_HEADLINE_THRESHOLD, APP_AUTO_CONFIRM_THRESHOLD)


def load_verified_manifest(
    manifest_path: str | Path, *, test_root: str | Path
) -> dict[str, Any]:
    """Load a frozen manifest and refuse it unless every pinned image verifies."""

    path = Path(manifest_path)
    problems = verify_frozen_test_manifest(path, data_root=test_root)
    if problems:
        shown = "\n".join(problems[:20])
        raise TargetTestSetError(
            f"frozen test manifest failed verification ({len(problems)} problems):\n{shown}"
        )
    document = json.loads(path.read_text(encoding="utf-8"))
    if tuple(document.get("ontology_class_names", ())) != EXPECTED_CLASSES:
        raise TargetTestSetError("manifest class names do not match the frozen ontology")
    if document.get("role") != "target_test" or document.get("include_in_training"):
        raise TargetTestSetError("manifest is not an evaluation-only target test set")
    return document


def _image_file_name(image: Mapping[str, Any]) -> str:
    return Path(str(image["relative_path"])).name


def label_lines(image: Mapping[str, Any]) -> list[str]:
    """YOLO label lines for one manifest image, in canonical class IDs."""

    lines = []
    for box in image["boxes"]:
        lines.append(
            f"{int(box['canonical_class_id'])} {float(box['x_center']):.6f} "
            f"{float(box['y_center']):.6f} {float(box['width']):.6f} "
            f"{float(box['height']):.6f}"
        )
    return lines


def build_eval_dataset(
    manifest: Mapping[str, Any],
    *,
    test_root: str | Path,
    destination: str | Path,
) -> Path:
    """Materialize ``images/`` and ``labels/`` plus ``dataset.yaml`` for validation.

    Images are hard-linked where possible (copied otherwise) so the evaluated
    bytes are exactly the frozen ones. An existing directory is reused only if
    it was built from the same manifest checksum; anything else is refused.
    """

    root = Path(test_root)
    output = Path(destination)
    marker_path = output / EVAL_DATASET_MARKER
    checksum = manifest.get("manifest_checksum")
    if output.exists():
        if marker_path.is_file():
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            if marker.get("manifest_checksum") == checksum:
                return output / "dataset.yaml"
        raise FileExistsError(
            f"refusing to reuse {output}: it was not built from manifest {checksum}"
        )

    names = [_image_file_name(image) for image in manifest["images"]]
    if len(set(names)) != len(names):
        raise TargetTestSetError("manifest image file names are not unique")

    images_dir = output / "images"
    labels_dir = output / "labels"
    images_dir.mkdir(parents=True)
    labels_dir.mkdir()
    for image, name in zip(manifest["images"], names):
        source = root / str(image["relative_path"])
        target = images_dir / name
        try:
            os.link(source, target)
        except OSError:
            shutil.copy2(source, target)
        (labels_dir / f"{Path(name).stem}.txt").write_text(
            "\n".join(label_lines(image)) + "\n", encoding="utf-8"
        )

    dataset = {
        "path": str(output.resolve()),
        # Ultralytics requires a train key; evaluation reads only val.
        "train": "images",
        "val": "images",
        "names": {index: name for index, name in enumerate(EXPECTED_CLASSES)},
    }
    with (output / "dataset.yaml").open("x", encoding="utf-8") as handle:
        yaml.safe_dump(dataset, handle, sort_keys=False)
    marker_path.write_text(
        json.dumps(
            {
                "manifest_id": manifest.get("manifest_id"),
                "manifest_checksum": checksum,
                "images": len(names),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return output / "dataset.yaml"


@dataclass(frozen=True)
class Top1Outcome:
    threshold: float
    images: int
    correct: int
    wrong: int
    abstained: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "confidence_threshold": self.threshold,
            "images": self.images,
            "correct": self.correct,
            "wrong": self.wrong,
            "abstained": self.abstained,
            "correct_rate": round(self.correct / self.images, 4) if self.images else None,
            "answered_accuracy": (
                round(self.correct / (self.correct + self.wrong), 4)
                if self.correct + self.wrong
                else None
            ),
        }


def score_top1(
    manifest: Mapping[str, Any],
    predictions: Mapping[str, Sequence[tuple[int, float]]],
    *,
    thresholds: Iterable[float] = TOP1_THRESHOLDS,
) -> list[Top1Outcome]:
    """Score the single most confident detection per image.

    ``predictions`` maps an image file name to ``(class_id, confidence)``
    pairs. At each threshold, an image is *correct* when its top detection
    reaches the threshold and its class appears among that image's true
    classes, *wrong* when it reaches the threshold with any other class, and
    *abstained* when no detection reaches the threshold.
    """

    truths = {
        _image_file_name(image): {int(box["canonical_class_id"]) for box in image["boxes"]}
        for image in manifest["images"]
    }
    missing = set(predictions) - set(truths)
    if missing:
        raise ValueError(f"predictions for images not in the manifest: {sorted(missing)[:5]}")

    outcomes = []
    for threshold in thresholds:
        correct = wrong = abstained = 0
        for name, true_classes in truths.items():
            detections = predictions.get(name, ())
            top = max(detections, key=lambda item: item[1], default=None)
            if top is None or top[1] < threshold:
                abstained += 1
            elif int(top[0]) in true_classes:
                correct += 1
            else:
                wrong += 1
        outcomes.append(Top1Outcome(threshold, len(truths), correct, wrong, abstained))
    return outcomes
