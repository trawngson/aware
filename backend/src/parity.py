"""Framework-neutral checks for server-to-Core-ML detection parity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .canonical_data import NormalizedBox
from .metadata_validation import EXPECTED_CLASSES


@dataclass(frozen=True)
class Prediction:
    class_id: int
    confidence: float
    box: NormalizedBox


@dataclass(frozen=True)
class ParityIssue:
    image_id: str
    code: str
    detail: str


@dataclass(frozen=True)
class ParityReport:
    issues: tuple[ParityIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.issues

    def render(self) -> str:
        lines = [f"Core ML parity: {'PASS' if self.ok else 'FAIL'}"]
        lines.extend(f"- {item.image_id} {item.code}: {item.detail}" for item in self.issues)
        return "\n".join(lines)


def validate_exported_labels(labels: Sequence[str]) -> tuple[str, ...]:
    expected = tuple(EXPECTED_CLASSES)
    actual = tuple(labels)
    if actual == expected:
        return ()
    return (f"expected labels {expected}, got {actual}",)


def intersection_over_union(left: NormalizedBox, right: NormalizedBox) -> float:
    intersection_width = max(0.0, min(left.xmax, right.xmax) - max(left.xmin, right.xmin))
    intersection_height = max(0.0, min(left.ymax, right.ymax) - max(left.ymin, right.ymin))
    intersection = intersection_width * intersection_height
    union = left.width * left.height + right.width * right.height - intersection
    return intersection / union if union > 0 else 0.0


def compare_predictions(
    server: Mapping[str, Sequence[Prediction]],
    coreml: Mapping[str, Sequence[Prediction]],
    *,
    confidence_tolerance: float = 0.05,
    minimum_box_iou: float = 0.95,
) -> ParityReport:
    issues: list[ParityIssue] = []
    if set(server) != set(coreml):
        missing = sorted(set(server) - set(coreml))
        extra = sorted(set(coreml) - set(server))
        issues.append(ParityIssue("<set>", "image_set_mismatch", f"missing={missing} extra={extra}"))

    for image_id in sorted(set(server) & set(coreml)):
        server_items = list(server[image_id])
        coreml_items = list(coreml[image_id])
        if not server_items and coreml_items:
            issues.append(ParityIssue(image_id, "empty_output_mismatch", "server empty, Core ML non-empty"))
            continue
        unmatched = set(range(len(coreml_items)))
        for expected in server_items:
            candidates = [
                index
                for index in unmatched
                if coreml_items[index].class_id == expected.class_id
            ]
            if not candidates:
                issues.append(
                    ParityIssue(image_id, "missing_detection", f"class_id={expected.class_id}")
                )
                continue
            best = max(candidates, key=lambda index: intersection_over_union(expected.box, coreml_items[index].box))
            actual = coreml_items[best]
            unmatched.remove(best)
            iou = intersection_over_union(expected.box, actual.box)
            if iou < minimum_box_iou:
                issues.append(ParityIssue(image_id, "box_mismatch", f"IoU={iou:.4f}"))
            delta = abs(expected.confidence - actual.confidence)
            if delta > confidence_tolerance:
                issues.append(ParityIssue(image_id, "confidence_mismatch", f"delta={delta:.4f}"))
        for index in sorted(unmatched):
            issues.append(
                ParityIssue(
                    image_id,
                    "extra_detection",
                    f"class_id={coreml_items[index].class_id}",
                )
            )
    return ParityReport(tuple(issues))


def _at_least(
    predictions: Mapping[str, Sequence[Prediction]], minimum: float
) -> dict[str, list[Prediction]]:
    return {
        image_id: [item for item in items if item.confidence >= minimum]
        for image_id, items in predictions.items()
    }


def compare_with_confidence_band(
    server: Mapping[str, Sequence[Prediction]],
    coreml: Mapping[str, Sequence[Prediction]],
    *,
    threshold: float = 0.25,
    band: float = 0.05,
    confidence_tolerance: float = 0.05,
    minimum_box_iou: float = 0.95,
) -> ParityReport:
    """Compare detections without penalizing ones that straddle the threshold.

    FP16 rounding can move a detection scored near ``threshold`` to the other
    side of it. A detection counts as missing (or extra) only when one side
    reports it at ``threshold + band`` or higher and the other side has no
    matching detection even at ``threshold - band``. Box and confidence
    agreement are checked for every clearly present server detection.
    """

    strict, loose = threshold + band, threshold - band
    forward = compare_predictions(
        _at_least(server, strict),
        _at_least(coreml, loose),
        confidence_tolerance=confidence_tolerance,
        minimum_box_iou=minimum_box_iou,
    )
    backward = compare_predictions(
        _at_least(coreml, strict),
        _at_least(server, loose),
        confidence_tolerance=confidence_tolerance,
        minimum_box_iou=minimum_box_iou,
    )
    issues = [
        item
        for item in forward.issues
        if item.code in {"image_set_mismatch", "missing_detection", "box_mismatch", "confidence_mismatch"}
    ]
    issues.extend(
        ParityIssue(item.image_id, "extra_detection", item.detail)
        for item in backward.issues
        if item.code == "missing_detection"
    )
    return ParityReport(tuple(issues))


def predictions_to_json(predictions: Mapping[str, Sequence[Prediction]]) -> dict[str, list[dict]]:
    return {
        image_id: [
            {
                "class_id": item.class_id,
                "confidence": round(float(item.confidence), 6),
                "xyxyn": [round(float(value), 6) for value in (item.box.xmin, item.box.ymin, item.box.xmax, item.box.ymax)],
            }
            for item in items
        ]
        for image_id, items in sorted(predictions.items())
    }


def predictions_from_json(document: Mapping[str, Sequence[Mapping]]) -> dict[str, list[Prediction]]:
    return {
        image_id: [
            Prediction(int(item["class_id"]), float(item["confidence"]), NormalizedBox(*map(float, item["xyxyn"])))
            for item in items
        ]
        for image_id, items in document.items()
    }
