from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.train_vast import _existing_weights, _validate_dataset_release
from src.metadata_validation import EXPECTED_CLASSES
from src.project_paths import ProjectPaths


class TrainingEntrypointTests(unittest.TestCase):
    def test_existing_approved_weights_must_stay_under_remote_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            data_root = root / "data"
            output_root = root / "output"
            project_root = root / "code"
            for directory in (data_root / "weights", output_root, project_root):
                directory.mkdir(parents=True)
            weights = data_root / "weights" / "yolo26n.pt"
            weights.write_bytes(b"fixture")
            outside = root / "yolo26n.pt"
            outside.write_bytes(b"fixture")
            paths = ProjectPaths(project_root, data_root, output_root)

            self.assertEqual(_existing_weights("weights/yolo26n.pt", paths), weights.resolve())
            with self.assertRaises(ValueError):
                _existing_weights(str(outside), paths)

    def test_audited_release_with_exact_labels_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            release = Path(temporary_directory) / "release-v1"
            (release / "images" / "train").mkdir(parents=True)
            (release / "images" / "val").mkdir(parents=True)
            manifests = release / "manifests"
            manifests.mkdir()
            dataset = {
                "path": str(release),
                "train": "images/train",
                "val": "images/val",
                "names": {index: name for index, name in enumerate(EXPECTED_CLASSES)},
            }
            dataset_path = release / "dataset.yaml"
            dataset_path.write_text(yaml.safe_dump(dataset), encoding="utf-8")
            (manifests / "audit_report.json").write_text(
                json.dumps({"ok": True}), encoding="utf-8"
            )
            (manifests / "split_manifest.json").write_text(
                json.dumps(
                    {
                        "split_version": "release-v1",
                        "seed": 26,
                        "leakage_violations": [],
                    }
                ),
                encoding="utf-8",
            )

            split_version, _ = _validate_dataset_release(dataset_path)

            self.assertEqual(split_version, "release-v1")

    def test_dataset_download_action_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            release = Path(temporary_directory)
            dataset_path = release / "dataset.yaml"
            dataset_path.write_text("download: unsafe-command\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "download"):
                _validate_dataset_release(dataset_path)


if __name__ == "__main__":
    unittest.main()
