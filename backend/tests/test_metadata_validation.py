from __future__ import annotations

import copy
import unittest
from pathlib import Path

from src.metadata_validation import (
    EXPECTED_CLASSES,
    load_yaml_mapping,
    validate_ontology,
    validate_source_manifest,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = PROJECT_ROOT / "tests" / "fixtures"


class OntologyValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ontology = load_yaml_mapping(PROJECT_ROOT / "ontology.yaml")

    def test_repository_ontology_is_valid_and_ordered(self) -> None:
        result = validate_ontology(self.ontology)

        self.assertTrue(result.ok, result.render("ontology"))
        self.assertEqual(
            tuple(item["name"] for item in self.ontology["classes"]),
            EXPECTED_CLASSES,
        )

    def test_changed_numeric_order_is_rejected(self) -> None:
        changed = copy.deepcopy(self.ontology)
        changed["classes"][0]["id"] = 1

        result = validate_ontology(changed)

        self.assertFalse(result.ok)
        self.assertIn("exactly 0 through 7", result.render("ontology"))

    def test_small_invalid_fixture_reports_missing_rules_and_classes(self) -> None:
        document = load_yaml_mapping(FIXTURES / "invalid_ontology.yaml")

        result = validate_ontology(document)

        self.assertFalse(result.ok)
        self.assertIn("global_annotation_rules.occlusion", result.render("ontology"))
        self.assertIn("exactly 8 classes", result.render("ontology"))


class SourceManifestValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ontology = load_yaml_mapping(PROJECT_ROOT / "ontology.yaml")
        self.manifest = load_yaml_mapping(PROJECT_ROOT / "source_manifest.yaml")

    def test_repository_source_manifest_is_valid(self) -> None:
        result = validate_source_manifest(
            self.manifest,
            ontology_version=self.ontology["ontology_version"],
        )

        self.assertTrue(result.ok, result.render("source manifest"))

    def test_legacy_source_cannot_enter_training(self) -> None:
        changed = copy.deepcopy(self.manifest)
        legacy = next(item for item in changed["sources"] if item["role"] == "legacy_evidence")
        legacy["include_in_training"] = True

        result = validate_source_manifest(changed)

        self.assertFalse(result.ok)
        self.assertIn("excluded sources cannot enter", result.render("source manifest"))

    def test_unsafe_source_path_is_rejected(self) -> None:
        document = load_yaml_mapping(FIXTURES / "invalid_source_manifest.yaml")

        result = validate_source_manifest(document)

        self.assertFalse(result.ok)
        rendered = result.render("source manifest")
        self.assertIn("safe relative path", rendered)
        self.assertIn("exactly two training sources", rendered)


if __name__ == "__main__":
    unittest.main()
