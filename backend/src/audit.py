"""Read-only audit checks for canonical detection records."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from .canonical_data import CanonicalImage, safe_relative_path
from .metadata_validation import EXPECTED_CLASSES


@dataclass(frozen=True)
class AuditFinding:
    severity: str
    code: str
    image_id: str
    detail: str


@dataclass(frozen=True)
class DatasetAuditReport:
    findings: tuple[AuditFinding, ...]
    image_counts_by_source: dict[str, int]
    annotation_counts_by_class: dict[str, int]

    @property
    def ok(self) -> bool:
        return not any(item.severity == "error" for item in self.findings)

    def render(self) -> str:
        lines = [f"dataset audit: {'PASS' if self.ok else 'FAIL'}"]
        lines.append(f"images by source: {self.image_counts_by_source}")
        lines.append(f"annotations by class: {self.annotation_counts_by_class}")
        for finding in self.findings:
            lines.append(
                f"[{finding.severity.upper()}] {finding.code} "
                f"{finding.image_id}: {finding.detail}"
            )
        return "\n".join(lines)


def audit_canonical_images(
    images: Sequence[CanonicalImage],
    *,
    source_roots: Mapping[str, Path] | None = None,
    required_classes: Sequence[str] | None = None,
    verify_image_files: bool = False,
) -> DatasetAuditReport:
    """Audit metadata and optional file presence without changing source data."""

    findings: list[AuditFinding] = []
    image_counts: Counter[str] = Counter()
    class_counts: Counter[str] = Counter()
    seen_image_ids: set[str] = set()

    for image in images:
        image_counts[image.source_id] += 1
        if image.image_id in seen_image_ids:
            findings.append(
                AuditFinding("error", "duplicate_image_id", image.image_id, "ID appears more than once")
            )
        seen_image_ids.add(image.image_id)

        if image.width <= 0 or image.height <= 0:
            findings.append(
                AuditFinding("error", "invalid_dimensions", image.image_id, "width and height must be positive")
            )
        try:
            relative_path = safe_relative_path(image.relative_path)
        except ValueError as error:
            findings.append(AuditFinding("error", "unsafe_path", image.image_id, str(error)))
            relative_path = ""

        if source_roots is not None:
            source_root = source_roots.get(image.source_id)
            if source_root is None:
                findings.append(
                    AuditFinding("error", "missing_source_root", image.image_id, image.source_id)
                )
            elif relative_path:
                image_path = source_root / relative_path
                if not image_path.is_file():
                    findings.append(
                        AuditFinding("error", "missing_image", image.image_id, relative_path)
                    )
                elif verify_image_files:
                    try:
                        from .image_files import visually_oriented_size

                        actual_size = visually_oriented_size(image_path)
                        if actual_size != (image.width, image.height):
                            findings.append(
                                AuditFinding(
                                    "error",
                                    "dimension_mismatch",
                                    image.image_id,
                                    f"metadata={(image.width, image.height)} "
                                    f"visually_oriented_file={actual_size}",
                                )
                            )
                    except (OSError, ValueError) as error:
                        findings.append(
                            AuditFinding(
                                "error",
                                "corrupt_image",
                                image.image_id,
                                type(error).__name__,
                            )
                        )

        if not image.annotations:
            findings.append(
                AuditFinding("error", "empty_annotations", image.image_id, "canonical image has no accepted boxes")
            )
        annotation_ids: set[str] = set()
        for annotation in image.annotations:
            if annotation.annotation_id in annotation_ids:
                findings.append(
                    AuditFinding(
                        "error",
                        "duplicate_annotation_id",
                        image.image_id,
                        annotation.annotation_id,
                    )
                )
            annotation_ids.add(annotation.annotation_id)
            if annotation.class_id not in range(len(EXPECTED_CLASSES)):
                findings.append(
                    AuditFinding(
                        "error",
                        "invalid_class_id",
                        image.image_id,
                        str(annotation.class_id),
                    )
                )
            elif EXPECTED_CLASSES[annotation.class_id] != annotation.class_name:
                findings.append(
                    AuditFinding(
                        "error",
                        "class_order_mismatch",
                        image.image_id,
                        f"{annotation.class_id} != {annotation.class_name}",
                    )
                )
            class_counts[annotation.class_name] += 1
            for error in annotation.box.validation_errors():
                findings.append(AuditFinding("error", "invalid_box", image.image_id, error))

    for class_name in required_classes or ():
        if class_counts[class_name] == 0:
            findings.append(
                AuditFinding(
                    "error",
                    "missing_required_class",
                    "<dataset>",
                    class_name,
                )
            )

    return DatasetAuditReport(
        findings=tuple(findings),
        image_counts_by_source=dict(sorted(image_counts.items())),
        annotation_counts_by_class=dict(sorted(class_counts.items())),
    )
