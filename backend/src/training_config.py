"""Validation and argument building for the approved v1 VAST training recipe."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .metadata_validation import MetadataIssue, MetadataValidationResult


APPROVED_TRAINING_SETTINGS: dict[str, Any] = {
    "imgsz": 640,
    "epochs": 200,
    "patience": 40,
    "batch": 64,
    "optimizer": "AdamW",
    "lr0": 0.001,
    "seed": 26,
    "deterministic": True,
    "workers": 8,
    "amp": True,
    "cache": False,
    "rect": False,
    "multi_scale": 0.0,
    "cos_lr": False,
    "close_mosaic": 10,
    "pretrained": True,
    "save": True,
    "save_period": 10,
    "plots": True,
    "val": True,
    "fraction": 1.0,
}

APPROVED_MODELS = ("yolo26n.pt", "yolo26s.pt")

APPROVED_SMOKE_SETTINGS: dict[str, Any] = {
    "epochs": 1,
    "fraction": 0.02,
    "batch": 16,
}


def validate_training_config(document: Mapping[str, Any]) -> MetadataValidationResult:
    """Fail closed if the reviewed controlled recipe has changed."""

    issues: list[MetadataIssue] = []
    if document.get("schema_version") != "1.0":
        issues.append(MetadataIssue("schema_version", "must equal '1.0'"))
    if document.get("configuration_id") != "aware-yolo26-v1-controlled":
        issues.append(MetadataIssue("configuration_id", "is not the approved v1 recipe"))
    if document.get("approval_status") != "approved":
        issues.append(MetadataIssue("approval_status", "must equal 'approved'"))

    hardware = document.get("hardware")
    if not isinstance(hardware, Mapping):
        issues.append(MetadataIssue("hardware", "must be a mapping"))
    else:
        expected_hardware = {
            "accelerator": "NVIDIA A100",
            "device": 0,
            "gpu_count": 1,
        }
        for field, expected in expected_hardware.items():
            if hardware.get(field) != expected:
                issues.append(MetadataIssue(f"hardware.{field}", f"must equal {expected!r}"))

    training = document.get("training")
    if not isinstance(training, Mapping):
        issues.append(MetadataIssue("training", "must be a mapping"))
    else:
        unexpected = set(training) - set(APPROVED_TRAINING_SETTINGS)
        missing = set(APPROVED_TRAINING_SETTINGS) - set(training)
        for field in sorted(unexpected):
            issues.append(MetadataIssue(f"training.{field}", "is not an approved setting"))
        for field in sorted(missing):
            issues.append(MetadataIssue(f"training.{field}", "is required"))
        for field, expected in APPROVED_TRAINING_SETTINGS.items():
            if field in training and training[field] != expected:
                issues.append(MetadataIssue(f"training.{field}", f"must equal {expected!r}"))

    smoke_test = document.get("smoke_test")
    if not isinstance(smoke_test, Mapping):
        issues.append(MetadataIssue("smoke_test", "must be a mapping"))
    else:
        unexpected = set(smoke_test) - set(APPROVED_SMOKE_SETTINGS)
        missing = set(APPROVED_SMOKE_SETTINGS) - set(smoke_test)
        for field in sorted(unexpected):
            issues.append(
                MetadataIssue(f"smoke_test.{field}", "is not an approved setting")
            )
        for field in sorted(missing):
            issues.append(MetadataIssue(f"smoke_test.{field}", "is required"))
        for field, expected in APPROVED_SMOKE_SETTINGS.items():
            if field in smoke_test and smoke_test[field] != expected:
                issues.append(
                    MetadataIssue(f"smoke_test.{field}", f"must equal {expected!r}")
                )

    policy = document.get("comparison_policy")
    if not isinstance(policy, Mapping):
        issues.append(MetadataIssue("comparison_policy", "must be a mapping"))
    else:
        if tuple(policy.get("models", ())) != APPROVED_MODELS:
            issues.append(MetadataIssue("comparison_policy.models", "must keep YOLO26n then YOLO26s"))
        if policy.get("use_identical_settings") is not True:
            issues.append(MetadataIssue("comparison_policy.use_identical_settings", "must be true"))
        if policy.get("batch_failure_action") != "lower_batch_for_both_models":
            issues.append(
                MetadataIssue(
                    "comparison_policy.batch_failure_action",
                    "must lower the batch for both models",
                )
            )

    return MetadataValidationResult(tuple(issues))


def training_arguments(document: Mapping[str, Any], *, smoke: bool = False) -> dict[str, Any]:
    """Return Ultralytics arguments only after the configuration passes validation."""

    result = validate_training_config(document)
    if not result.ok:
        raise ValueError(result.render("training configuration"))
    arguments = dict(document["training"])
    if smoke:
        arguments.update(document["smoke_test"])
    return arguments
