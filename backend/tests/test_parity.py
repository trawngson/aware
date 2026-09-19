from __future__ import annotations

import unittest

from src.canonical_data import NormalizedBox
from src.metadata_validation import EXPECTED_CLASSES
from src.parity import (
    Prediction,
    compare_predictions,
    compare_with_confidence_band,
    predictions_from_json,
    predictions_to_json,
    validate_exported_labels,
)


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

    def box(self) -> NormalizedBox:
        return NormalizedBox(0.1, 0.1, 0.5, 0.8)

    def test_band_ignores_detections_straddling_the_threshold(self) -> None:
        server = {"image": [Prediction(0, 0.27, self.box())]}
        coreml = {"image": [Prediction(0, 0.23, self.box())]}
        self.assertTrue(compare_with_confidence_band(server, coreml).ok)
        self.assertTrue(compare_with_confidence_band(server, {"image": []}).ok)

    def test_band_flags_clearly_missing_and_extra_detections(self) -> None:
        confident = Prediction(3, 0.8, self.box())
        missing = compare_with_confidence_band({"image": [confident]}, {"image": []})
        self.assertIn("missing_detection", missing.render())
        extra = compare_with_confidence_band({"image": []}, {"image": [confident]})
        self.assertIn("extra_detection", extra.render())

    def test_band_checks_box_and_confidence_agreement(self) -> None:
        server = {"image": [Prediction(1, 0.9, self.box())]}
        moved = {"image": [Prediction(1, 0.7, NormalizedBox(0.3, 0.3, 0.7, 0.9))]}
        rendered = compare_with_confidence_band(server, moved).render()
        self.assertIn("box_mismatch", rendered)
        self.assertIn("confidence_mismatch", rendered)

    def test_prediction_json_round_trip(self) -> None:
        original = {"a.png": [Prediction(2, 0.5, self.box())], "b.png": []}
        self.assertEqual(predictions_from_json(predictions_to_json(original)), original)


if __name__ == "__main__":
    unittest.main()
