"""Validation for the frozen ontology and source metadata.

The validators intentionally use only PyYAML plus the standard library so the
same checks can run locally and in the reviewed VAST notebook. They never read
dataset contents, create directories, or access the network.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

import yaml


EXPECTED_CLASSES = (
    "plastic_bottle",
    "glass_container",
    "metal_can",
    "cardboard",
    "plastic_container",
    "plastic_bag",
    "disposable_cup",
    "battery",
    "styrofoam",
)

REQUIRED_GLOBAL_RULES = (
    "bounding_box",
    "occlusion",
    "truncation",
    "damage",
    "contamination",
    "multiple_instances",
    "ambiguity",
    "caps",
)

REQUIRED_CLASS_FIELDS = (
    "id",
    "name",
    "definition",
    "positive",
    "negative",
    "ambiguity",
    "attached_parts",
)


@dataclass(frozen=True)
class MetadataIssue:
    path: str
    message: str

    def render(self) -> str:
        return f"{self.path}: {self.message}"


@dataclass(frozen=True)
class MetadataValidationResult:
    issues: tuple[MetadataIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.issues

    def render(self, label: str) -> str:
        if self.ok:
            return f"{label}: PASS"
        lines = [f"{label}: FAIL ({len(self.issues)} issue(s))"]
        lines.extend(f"- {issue.render()}" for issue in self.issues)
        return "\n".join(lines)


def load_yaml_mapping(path: str | Path) -> dict[str, Any]:
    """Load a YAML mapping without resolving paths or touching dataset data."""

    source = Path(path)
    with source.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{source} must contain a YAML mapping at its root")
    return value


def _nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_nonempty_text_list(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(_nonempty_text(item) for item in value)
    )


def _valid_iso_date(value: Any) -> bool:
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _safe_relative_path(value: Any) -> bool:
    if value is None:
        return True
    if not _nonempty_text(value):
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and "." not in path.parts


def _public_url(value: Any) -> bool:
    if not _nonempty_text(value):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def validate_ontology(document: Mapping[str, Any]) -> MetadataValidationResult:
    issues: list[MetadataIssue] = []

    if document.get("schema_version") != "1.0":
        issues.append(MetadataIssue("schema_version", "must equal '1.0'"))
    if not _nonempty_text(document.get("ontology_version")):
        issues.append(MetadataIssue("ontology_version", "must be non-empty"))
    if document.get("status") != "frozen":
        issues.append(MetadataIssue("status", "ontology v1 must be frozen"))

    id_policy = document.get("id_policy")
    if not isinstance(id_policy, Mapping):
        issues.append(MetadataIssue("id_policy", "must be a mapping"))
    else:
        for key in ("contiguous_from_zero", "ids_are_never_reused"):
            if id_policy.get(key) is not True:
                issues.append(MetadataIssue(f"id_policy.{key}", "must be true"))

    rules = document.get("global_annotation_rules")
    if not isinstance(rules, Mapping):
        issues.append(MetadataIssue("global_annotation_rules", "must be a mapping"))
    else:
        for key in REQUIRED_GLOBAL_RULES:
            if not _nonempty_text(rules.get(key)):
                issues.append(
                    MetadataIssue(f"global_annotation_rules.{key}", "must be non-empty")
                )

    classes = document.get("classes")
    if not isinstance(classes, list):
        return MetadataValidationResult(
            tuple(issues + [MetadataIssue("classes", "must be a list")])
        )
    if len(classes) != len(EXPECTED_CLASSES):
        issues.append(MetadataIssue("classes", "must contain exactly nine classes"))

    ids: list[Any] = []
    names: list[Any] = []
    for index, item in enumerate(classes):
        prefix = f"classes[{index}]"
        if not isinstance(item, Mapping):
            issues.append(MetadataIssue(prefix, "must be a mapping"))
            continue
        for field in REQUIRED_CLASS_FIELDS:
            if field not in item:
                issues.append(MetadataIssue(f"{prefix}.{field}", "is required"))
        ids.append(item.get("id"))
        names.append(item.get("name"))
        for field in ("definition", "ambiguity", "attached_parts"):
            if not _nonempty_text(item.get(field)):
                issues.append(MetadataIssue(f"{prefix}.{field}", "must be non-empty"))
        for field in ("positive", "negative"):
            if not _is_nonempty_text_list(item.get(field)):
                issues.append(
                    MetadataIssue(f"{prefix}.{field}", "must be a non-empty string list")
                )

    if ids != list(range(len(EXPECTED_CLASSES))):
        issues.append(MetadataIssue("classes[*].id", "must be exactly 0 through 8 in order"))
    if names != list(EXPECTED_CLASSES):
        issues.append(
            MetadataIssue(
                "classes[*].name",
                "must match the approved class names and numeric order",
            )
        )
    if len(set(ids)) != len(ids):
        issues.append(MetadataIssue("classes[*].id", "IDs must be unique"))
    if len(set(names)) != len(names):
        issues.append(MetadataIssue("classes[*].name", "names must be unique"))

    runtime_outcomes = document.get("runtime_outcomes_not_classes", [])
    if not isinstance(runtime_outcomes, list):
        issues.append(MetadataIssue("runtime_outcomes_not_classes", "must be a list"))
    elif set(names) & set(runtime_outcomes):
        issues.append(
            MetadataIssue(
                "runtime_outcomes_not_classes",
                "runtime outcomes must not also be training classes",
            )
        )

    return MetadataValidationResult(tuple(issues))


def validate_source_manifest(
    document: Mapping[str, Any],
    *,
    ontology_version: str | None = None,
) -> MetadataValidationResult:
    issues: list[MetadataIssue] = []

    if document.get("schema_version") != "1.0":
        issues.append(MetadataIssue("schema_version", "must equal '1.0'"))
    if not _nonempty_text(document.get("manifest_version")):
        issues.append(MetadataIssue("manifest_version", "must be non-empty"))
    if ontology_version and document.get("ontology_version") != ontology_version:
        issues.append(MetadataIssue("ontology_version", "must match ontology.yaml"))

    policy = document.get("policy")
    if not isinstance(policy, Mapping):
        issues.append(MetadataIssue("policy", "must be a mapping"))
        approved_ids: list[Any] = []
    else:
        for key in (
            "raw_data_immutable",
            "remote_data_only",
            "acquisition_requires_manual_review",
        ):
            if policy.get(key) is not True:
                issues.append(MetadataIssue(f"policy.{key}", "must be true"))
        if policy.get("unidentified_sources_allowed") is not False:
            issues.append(
                MetadataIssue("policy.unidentified_sources_allowed", "must be false")
            )
        approved_ids = policy.get("approved_training_source_ids", [])
        if not _is_nonempty_text_list(approved_ids):
            issues.append(
                MetadataIssue(
                    "policy.approved_training_source_ids",
                    "must be a non-empty string list",
                )
            )
            approved_ids = []

    sources = document.get("sources")
    if not isinstance(sources, list):
        return MetadataValidationResult(
            tuple(issues + [MetadataIssue("sources", "must be a list")])
        )

    seen_ids: set[str] = set()
    approved_from_records: set[str] = set()
    target_tests = 0
    excluded_legacy = 0

    for index, source in enumerate(sources):
        prefix = f"sources[{index}]"
        if not isinstance(source, Mapping):
            issues.append(MetadataIssue(prefix, "must be a mapping"))
            continue

        source_id = source.get("id")
        if not _nonempty_text(source_id):
            issues.append(MetadataIssue(f"{prefix}.id", "must be non-empty"))
            continue
        if source_id in seen_ids:
            issues.append(MetadataIssue(f"{prefix}.id", "must be unique"))
        seen_ids.add(source_id)

        role = source.get("role")
        approval = source.get("approval_status")
        include_training = source.get("include_in_training")
        include_evaluation = source.get("include_in_evaluation")

        for field in ("name", "owner", "version", "mapping_ledger_version"):
            if not _nonempty_text(source.get(field)):
                issues.append(MetadataIssue(f"{prefix}.{field}", "must be non-empty"))
        for field in ("published_date", "accessed_date"):
            if not _valid_iso_date(source.get(field)):
                issues.append(MetadataIssue(f"{prefix}.{field}", "must be ISO YYYY-MM-DD or null"))

        if role == "training" and approval == "approved":
            approved_from_records.add(source_id)
            if include_training is not True or include_evaluation is not False:
                issues.append(
                    MetadataIssue(
                        prefix,
                        "approved training sources must train=true and evaluation=false",
                    )
                )
            if not _public_url(source.get("stable_url")):
                issues.append(MetadataIssue(f"{prefix}.stable_url", "must be a public HTTPS URL"))
            if str(source.get("owner", "")).lower() == "unknown":
                issues.append(MetadataIssue(f"{prefix}.owner", "approved source owner cannot be unknown"))

        if approval == "excluded":
            if include_training is not False or include_evaluation is not False:
                issues.append(MetadataIssue(prefix, "excluded sources cannot enter training or evaluation"))
            if role == "legacy_evidence":
                excluded_legacy += 1

        license_record = source.get("license")
        if not isinstance(license_record, Mapping):
            issues.append(MetadataIssue(f"{prefix}.license", "must be a mapping"))
        elif role == "training" and approval == "approved":
            if license_record.get("spdx") in (None, "NOASSERTION"):
                issues.append(MetadataIssue(f"{prefix}.license.spdx", "approved source needs a license"))
            if license_record.get("verification_status") in (None, "pending", "failed"):
                issues.append(MetadataIssue(f"{prefix}.license.verification_status", "must pass a license gate"))

        annotations = source.get("original_annotations")
        if not isinstance(annotations, Mapping):
            issues.append(MetadataIssue(f"{prefix}.original_annotations", "must be a mapping"))
        else:
            for field in ("format", "class_list_reference"):
                if not _nonempty_text(annotations.get(field)):
                    issues.append(MetadataIssue(f"{prefix}.original_annotations.{field}", "must be non-empty"))

        acquisition = source.get("acquisition")
        if not isinstance(acquisition, Mapping):
            issues.append(MetadataIssue(f"{prefix}.acquisition", "must be a mapping"))
        else:
            if not _safe_relative_path(acquisition.get("raw_subdirectory")):
                issues.append(
                    MetadataIssue(
                        f"{prefix}.acquisition.raw_subdirectory",
                        "must be a safe relative path or null",
                    )
                )
            if role == "training" and approval == "approved":
                method = str(acquisition.get("method", ""))
                if not method.startswith("manual_remote"):
                    issues.append(
                        MetadataIssue(
                            f"{prefix}.acquisition.method",
                            "approved acquisition must be manual and remote",
                        )
                    )

        if source.get("preprocessing") != [] or source.get("augmentation") != []:
            issues.append(
                MetadataIssue(prefix, "raw source records must not apply preprocessing or augmentation")
            )
        if not _is_nonempty_text_list(source.get("limitations")):
            issues.append(MetadataIssue(f"{prefix}.limitations", "must be a non-empty string list"))

        if role == "target_test":
            target_tests += 1
            counts = source.get("counts", {})
            freeze = source.get("freeze_requirements", {})
            if include_training is not False or include_evaluation is not True:
                issues.append(MetadataIssue(prefix, "target test must be evaluation-only"))
            if not isinstance(counts, Mapping) or counts.get("minimum_images_per_class", 0) < 10:
                issues.append(MetadataIssue(f"{prefix}.counts", "must require at least 10 images per class"))
            if not isinstance(counts, Mapping) or counts.get("minimum_total_images", 0) < 90:
                issues.append(MetadataIssue(f"{prefix}.counts", "must require at least 90 images total"))
            if not isinstance(freeze, Mapping) or freeze.get("frozen_before_model_comparison") is not True:
                issues.append(MetadataIssue(f"{prefix}.freeze_requirements", "must freeze before comparison"))

    if set(approved_ids) != approved_from_records:
        issues.append(
            MetadataIssue(
                "policy.approved_training_source_ids",
                "must exactly match approved training source records",
            )
        )
    if len(approved_from_records) != 2:
        issues.append(MetadataIssue("sources", "v1 must approve exactly two training sources"))
    if target_tests != 1:
        issues.append(MetadataIssue("sources", "must define exactly one target-domain test source"))
    if excluded_legacy < 1:
        issues.append(MetadataIssue("sources", "must preserve at least one excluded legacy record"))

    return MetadataValidationResult(tuple(issues))
