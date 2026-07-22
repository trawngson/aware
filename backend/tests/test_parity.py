from __future__ import annotations

import unittest

from src.canonical_data import NormalizedBox
from src.metadata_validation import EXPECTED_CLASSES
from src.parity import Prediction, compare_predictions, validate_exported_labels


class ParityTests(unittest.TestCase):
    def test_exact_label_order_passes_and_reordered_labels_fail(self) -> None:
        self.assertEqual(validate_exported_labels(EXPECTED_CLASSES), ())
        reordered = list(EXPECTED_CLASSES)
        reordered[0], reordered[1] = reordered[1], reordered[0]
        self.assertTrue(validate_exported_labels(reordered))

    def test_close_predictions_and_empty_outputs_pass(self) -> None:
        server = {
            "detected": [Prediction(0, 0.9, NormalizedBox(0.1, 0.1, 0.5, 0.8))],
            "empty": [],
        }
        coreml = {
            "detected": [Prediction(0, 0.88, NormalizedBox(0.1, 0.1, 0.5, 0.8))],
            "empty": [],
        }

        report = compare_predictions(server, coreml)

        self.assertTrue(report.ok, report.render())

    def test_nms_or_empty_output_difference_fails(self) -> None:
        extra = Prediction(2, 0.8, NormalizedBox(0.2, 0.2, 0.4, 0.4))
        report = compare_predictions({"image": []}, {"image": [extra]})

        self.assertFalse(report.ok)
        self.assertIn("empty_output_mismatch", report.render())


if __name__ == "__main__":
    unittest.main()
