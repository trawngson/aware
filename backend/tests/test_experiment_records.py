from __future__ import annotations

import unittest
from pathlib import Path

from src.experiment_records import validate_experiment_record
from src.metadata_validation import load_yaml_mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ExperimentRecordTests(unittest.TestCase):
    def test_unfilled_template_fails_closed(self) -> None:
        template = load_yaml_mapping(PROJECT_ROOT / "records" / "experiment.template.yaml")

        result = validate_experiment_record(template)

        self.assertFalse(result.ok)
        self.assertIn("must be recorded", result.render("experiment"))

    def test_complete_controlled_record_passes(self) -> None:
        record = {
            "schema_version": "1.0",
            "run_id": "e1-yolo26n-seed26",
            "run_kind": "full",
            "status": "planned",
            "model": "yolo26n.pt",
            "ontology_version": "aware-ontology-v2",
            "source_manifest_version": "aware-sources-v2",
            "split_version": "aware-splits-v1",
            "code_revision": "0123456789abcdef",
            "training": {
                "image_size": 640,
                "seed": 26,
                "deterministic": True,
                "epochs": 200,
                "patience": 40,
                "batch": 64,
                "optimizer": "AdamW",
                "initial_learning_rate": 0.001,
                "config_file": "configs/training/v1_controlled.yaml",
            },
        }

        result = validate_experiment_record(record)

        self.assertTrue(result.ok, result.render("experiment"))

    def test_changed_controlled_setting_is_rejected(self) -> None:
        record = {
            "schema_version": "1.0",
            "run_id": "e2-yolo26s-seed26",
            "run_kind": "full",
            "status": "planned",
            "model": "yolo26s.pt",
            "ontology_version": "aware-ontology-v2",
            "source_manifest_version": "aware-sources-v2",
            "split_version": "aware-splits-v1",
            "code_revision": "0123456789abcdef",
            "training": {
                "image_size": 640,
                "seed": 26,
                "deterministic": True,
                "epochs": 300,
                "patience": 40,
                "batch": 64,
                "optimizer": "AdamW",
                "initial_learning_rate": 0.001,
                "config_file": "configs/training/v1_controlled.yaml",
            },
        }

        result = validate_experiment_record(record)

        self.assertFalse(result.ok)
        self.assertIn("training.epochs", result.render("experiment"))

    def test_retired_ontology_version_is_rejected(self) -> None:
        record = {
            "schema_version": "1.0",
            "run_id": "e3-yolo26n-seed26",
            "run_kind": "smoke",
            "status": "planned",
            "model": "yolo26n.pt",
            "ontology_version": "aware-ontology-v1",
            "source_manifest_version": "aware-sources-v2",
            "split_version": "aware-splits-v1",
            "code_revision": "0123456789abcdef",
            "training": {
                "image_size": 640,
                "seed": 26,
                "deterministic": True,
                "epochs": 1,
                "patience": 40,
                "batch": 64,
                "optimizer": "AdamW",
                "initial_learning_rate": 0.001,
                "config_file": "configs/training/v1_controlled.yaml",
            },
        }

        result = validate_experiment_record(record)

        self.assertFalse(result.ok)
        self.assertIn("ontology_version", result.render("experiment"))


if __name__ == "__main__":
    unittest.main()
