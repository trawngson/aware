"""Validation for recorded VAST experiments."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .metadata_validation import (
    EXPECTED_ONTOLOGY_VERSION,
    EXPECTED_SOURCE_MANIFEST_VERSION,
    MetadataIssue,
    MetadataValidationResult,
)


def validate_experiment_record(document: Mapping[str, Any]) -> MetadataValidationResult:
    issues: list[MetadataIssue] = []
    required_text = (
        "run_id",
        "ontology_version",
        "source_manifest_version",
        "split_version",
        "code_revision",
    )
    if document.get("schema_version") != "1.0":
        issues.append(MetadataIssue("schema_version", "must equal '1.0'"))
    for field in required_text:
        value = document.get(field)
        if not isinstance(value, str) or not value.strip() or "replace-before-run" in value:
            issues.append(MetadataIssue(field, "must be recorded before a run"))
    expected_versions = {
        "ontology_version": EXPECTED_ONTOLOGY_VERSION,
        "source_manifest_version": EXPECTED_SOURCE_MANIFEST_VERSION,
    }
    for field, expected in expected_versions.items():
        value = document.get(field)
        if isinstance(value, str) and value.strip() and "replace-before-run" not in value:
            if value != expected:
                issues.append(MetadataIssue(field, f"must equal {expected!r}"))
    if document.get("model") not in {"yolo26n.pt", "yolo26s.pt"}:
        issues.append(MetadataIssue("model", "must be yolo26n.pt or yolo26s.pt"))
    if document.get("status") not in {"planned", "running", "completed", "failed", "cancelled"}:
        issues.append(MetadataIssue("status", "is invalid"))
    run_kind = document.get("run_kind")
    if run_kind not in {"full", "smoke"}:
        issues.append(MetadataIssue("run_kind", "must be full or smoke"))

    training = document.get("training")
    if not isinstance(training, Mapping):
        issues.append(MetadataIssue("training", "must be a mapping"))
    else:
        if training.get("image_size") != 640:
            issues.append(MetadataIssue("training.image_size", "must equal 640 for v1 comparison"))
        expected = {
            "seed": 26,
            "deterministic": True,
            "epochs": 1 if run_kind == "smoke" else 200,
            "patience": 40,
            "batch": 64,
            "optimizer": "AdamW",
            "initial_learning_rate": 0.001,
        }
        for field, value in expected.items():
            if training.get(field) != value:
                issues.append(MetadataIssue(f"training.{field}", f"must equal {value!r}"))
        config_file = training.get("config_file")
        if config_file != "configs/training/v1_controlled.yaml":
            issues.append(
                MetadataIssue(
                    "training.config_file",
                    "must reference the approved v1 controlled configuration",
                )
            )

    return MetadataValidationResult(tuple(issues))
