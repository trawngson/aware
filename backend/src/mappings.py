"""Mapping-ledger validation and resolution."""

from __future__ import annotations

from collections.abc import Mapping
from collections import Counter
from dataclasses import dataclass
from typing import Any

from .metadata_validation import EXPECTED_CLASSES, MetadataIssue, MetadataValidationResult


ALLOWED_ACTIONS = frozenset({"keep", "safe_merge", "manual_review", "reject"})
ALLOWED_REVIEW_STATES = frozenset(
    {"approved", "representative_samples_required", "unresolved"}
)


@dataclass(frozen=True)
class MappingDecision:
    source: str
    source_class: str
    canonical_class: str | None
    action: str
    reason: str
    review_status: str

    @property
    def include_automatically(self) -> bool:
        return self.action in {"keep", "safe_merge"} and self.review_status == "approved"


def validate_mapping_ledger(document: Mapping[str, Any]) -> MetadataValidationResult:
    issues: list[MetadataIssue] = []
    if document.get("schema_version") != "1.0":
        issues.append(MetadataIssue("schema_version", "must equal '1.0'"))
    for field in ("mapping_ledger_version", "ontology_version"):
        if not isinstance(document.get(field), str) or not document[field].strip():
            issues.append(MetadataIssue(field, "must be non-empty"))

    mappings = document.get("mappings")
    if not isinstance(mappings, list):
        return MetadataValidationResult(
            tuple(issues + [MetadataIssue("mappings", "must be a list")])
        )

    seen: set[tuple[str, str]] = set()
    source_counts: Counter[str] = Counter()
    for index, entry in enumerate(mappings):
        prefix = f"mappings[{index}]"
        if not isinstance(entry, Mapping):
            issues.append(MetadataIssue(prefix, "must be a mapping"))
            continue
        source = entry.get("source")
        source_class = entry.get("source_class")
        canonical = entry.get("canonical_class")
        action = entry.get("action")
        review = entry.get("review_status")
        reason = entry.get("reason")

        if not isinstance(source, str) or not source.strip():
            issues.append(MetadataIssue(f"{prefix}.source", "must be non-empty"))
        if not isinstance(source_class, str) or not source_class.strip():
            issues.append(MetadataIssue(f"{prefix}.source_class", "must be non-empty"))
        key = (str(source), str(source_class))
        if key in seen:
            issues.append(MetadataIssue(prefix, "source/source_class pair must be unique"))
        seen.add(key)
        source_counts[str(source)] += 1

        if action not in ALLOWED_ACTIONS:
            issues.append(MetadataIssue(f"{prefix}.action", "is not an allowed action"))
        if review not in ALLOWED_REVIEW_STATES:
            issues.append(MetadataIssue(f"{prefix}.review_status", "is not an allowed state"))
        if not isinstance(reason, str) or not reason.strip():
            issues.append(MetadataIssue(f"{prefix}.reason", "must be non-empty"))
        if canonical is not None and canonical not in EXPECTED_CLASSES:
            issues.append(MetadataIssue(f"{prefix}.canonical_class", "is not in ontology v1"))
        if action in {"keep", "safe_merge"} and canonical is None:
            issues.append(MetadataIssue(f"{prefix}.canonical_class", "is required for included mappings"))
        if action == "reject" and canonical is not None:
            issues.append(MetadataIssue(f"{prefix}.canonical_class", "must be null for rejected mappings"))

    expected_counts = document.get("expected_source_class_counts")
    if not isinstance(expected_counts, Mapping):
        issues.append(MetadataIssue("expected_source_class_counts", "must be a mapping"))
    else:
        normalized_expected = {str(key): value for key, value in expected_counts.items()}
        if normalized_expected != dict(source_counts):
            issues.append(
                MetadataIssue(
                    "expected_source_class_counts",
                    f"expected {normalized_expected}, found {dict(source_counts)}",
                )
            )

    return MetadataValidationResult(tuple(issues))


class MappingTable:
    def __init__(self, decisions: list[MappingDecision]) -> None:
        self._decisions = {
            (decision.source, decision.source_class): decision for decision in decisions
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "MappingTable":
        result = validate_mapping_ledger(document)
        if not result.ok:
            raise ValueError(result.render("mapping ledger"))
        decisions = [MappingDecision(**entry) for entry in document["mappings"]]
        return cls(decisions)

    def resolve(self, source: str, source_class: str) -> MappingDecision:
        try:
            return self._decisions[(source, source_class)]
        except KeyError as error:
            raise KeyError(
                f"unmapped source class {source!r}/{source_class!r}; fail closed"
            ) from error
