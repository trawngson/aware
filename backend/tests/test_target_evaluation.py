from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from src.metadata_validation import EXPECTED_CLASSES
from src.target_evaluation import (
    EVAL_DATASET_MARKER,
    build_eval_dataset,
    label_lines,
    load_verified_manifest,
    score_top1,
)
from src.target_test_set import (
    TargetTestSetError,
    ingest_target_test_set,
    write_frozen_test_manifest,
)
from tests.test_target_test_set import FIXTURE_CLASS_ORDER, TargetTestSetHarness


class FrozenManifestHarness(TargetTestSetHarness):
    """Freezes the three-image fixture so evaluation code sees a real manifest."""

    def setUp(self) -> None:
        super().setUp()
        report = ingest_target_test_set(
            self.paths,
            class_order=FIXTURE_CLASS_ORDER,
            accepted_list_path=self.fixture / "accepted_images.txt",
            labels_root=self.fixture / "labels",
            image_roots={
                1: self.fixture / "images" / "Session 1",
                2: self.fixture / "images" / "Session 2",
            },
            expected_image_count=3,
        )
        self.assertTrue(report.ok, report.render())
        self.manifest_path = write_frozen_test_manifest(
            report, self.output_root / "frozen", paths=self.paths, manifest_id="fixture-v1"
        )
        self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))


class LoadVerifiedManifestTests(FrozenManifestHarness):
    def test_accepts_intact_manifest(self) -> None:
        document = load_verified_manifest(self.manifest_path, test_root=self.data_root)
        self.assertEqual(document["manifest_id"], "fixture-v1")

    def test_refuses_changed_image_bytes(self) -> None:
        image = self.data_root / self.manifest["images"][0]["relative_path"]
        image.write_bytes(image.read_bytes() + b"tampered")
        with self.assertRaises(TargetTestSetError):
            load_verified_manifest(self.manifest_path, test_root=self.data_root)


class BuildEvalDatasetTests(FrozenManifestHarness):
    def build(self) -> Path:
        return build_eval_dataset(
            self.manifest, test_root=self.data_root, destination=self.output_root / "eval"
        )

    def test_writes_images_labels_and_ontology_names(self) -> None:
        dataset_yaml = self.build()
        document = yaml.safe_load(dataset_yaml.read_text(encoding="utf-8"))
        self.assertEqual(tuple(document["names"][i] for i in sorted(document["names"])), EXPECTED_CLASSES)
        root = dataset_yaml.parent
        self.assertEqual(len(list((root / "images").iterdir())), 3)
        for image in self.manifest["images"]:
            stem = Path(image["relative_path"]).stem
            written = (root / "labels" / f"{stem}.txt").read_text(encoding="utf-8").split("\n")
            self.assertEqual([line for line in written if line], label_lines(image))

    def test_reuses_directory_built_from_same_manifest(self) -> None:
        first = self.build()
        self.assertEqual(self.build(), first)

    def test_refuses_directory_from_another_manifest(self) -> None:
        dataset_yaml = self.build()
        marker = dataset_yaml.parent / EVAL_DATASET_MARKER
        marker.write_text(json.dumps({"manifest_checksum": "other"}), encoding="utf-8")
        with self.assertRaises(FileExistsError):
            self.build()

    def test_refuses_unmarked_existing_directory(self) -> None:
        (self.output_root / "eval").mkdir(parents=True)
        with self.assertRaises(FileExistsError):
            self.build()


class ScoreTop1Tests(unittest.TestCase):
    manifest = {
        "images": [
            {"relative_path": "s/a.png", "boxes": [{"canonical_class_id": 0}]},
            {"relative_path": "s/b.png", "boxes": [{"canonical_class_id": 2}, {"canonical_class_id": 3}]},
            {"relative_path": "s/c.png", "boxes": [{"canonical_class_id": 4}]},
            {"relative_path": "s/d.png", "boxes": [{"canonical_class_id": 6}]},
        ]
    }

    def test_counts_correct_wrong_and_abstained_per_threshold(self) -> None:
        predictions = {
            "a.png": [(1, 0.30), (0, 0.90)],  # top is class 0 at 0.90: correct at both
            "b.png": [(3, 0.50)],  # any true class counts: correct at 0.25, abstain at 0.75
            "c.png": [(5, 0.80)],  # confidently wrong at both thresholds
            # d.png has no detections: abstained at both
        }
        low, high = score_top1(self.manifest, predictions, thresholds=(0.25, 0.75))
        self.assertEqual((low.correct, low.wrong, low.abstained), (2, 1, 1))
        self.assertEqual((high.correct, high.wrong, high.abstained), (1, 1, 2))
        self.assertEqual(low.as_dict()["correct_rate"], 0.5)
        self.assertEqual(high.as_dict()["answered_accuracy"], 0.5)

    def test_rejects_predictions_for_unknown_images(self) -> None:
        with self.assertRaises(ValueError):
            score_top1(self.manifest, {"zzz.png": [(0, 0.9)]})


if __name__ == "__main__":
    unittest.main()
