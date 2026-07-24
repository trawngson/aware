from __future__ import annotations

import copy
import unittest
from pathlib import Path

from src.metadata_validation import load_yaml_mapping
from src.training_config import training_arguments, validate_training_config


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TrainingConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_yaml_mapping(
            PROJECT_ROOT / "configs" / "training" / "v1_controlled.yaml"
        )

    def test_approved_configuration_passes(self) -> None:
        result = validate_training_config(self.config)

        self.assertTrue(result.ok, result.render("training configuration"))

    def test_changed_epoch_or_batch_fails_closed(self) -> None:
        changed = copy.deepcopy(self.config)
        changed["training"]["epochs"] = 300
        changed["training"]["batch"] = 32

        result = validate_training_config(changed)

        self.assertFalse(result.ok)
        self.assertIn("training.epochs", result.render("training configuration"))
        self.assertIn("training.batch", result.render("training configuration"))

    def test_smoke_arguments_use_the_approved_reduced_batch(self) -> None:
        arguments = training_arguments(self.config, smoke=True)

        self.assertEqual(arguments["epochs"], 1)
        self.assertEqual(arguments["fraction"], 0.02)
        self.assertEqual(arguments["batch"], 16)
        self.assertEqual(arguments["seed"], 26)
        self.assertTrue(arguments["deterministic"])

    def test_changed_smoke_batch_fails_closed(self) -> None:
        changed = copy.deepcopy(self.config)
        changed["smoke_test"]["batch"] = 8

        result = validate_training_config(changed)

        self.assertFalse(result.ok)
        self.assertIn(
            "smoke_test.batch",
            result.render("training configuration"),
        )


if __name__ == "__main__":
    unittest.main()
