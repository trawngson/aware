from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from src.audit import audit_canonical_images
from src.canonical_data import CanonicalAnnotation, CanonicalImage, NormalizedBox
from src.release import write_yolo_release


class ReleaseTests(unittest.TestCase):
    def test_release_is_new_immutable_and_keeps_class_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            source.mkdir()
            image_file = source / "image.jpg"
            image_file.write_bytes(b"fixture")
            image = CanonicalImage(
                image_id="fixture:1",
                source_id="fixture",
                source_version="v1",
                relative_path="image.jpg",
                width=100,
                height=100,
                group_id="capture-1",
                annotations=(
                    CanonicalAnnotation(
                        "1",
                        "Clear plastic bottle",
                        0,
                        "plastic_bottle",
                        NormalizedBox(0.1, 0.2, 0.5, 0.8),
                    ),
                ),
            )
            audit = audit_canonical_images([image], source_roots={"fixture": source})
            destination = root / "release"

            write_yolo_release(
                [image],
                {"fixture:1": "train"},
                {"fixture": source},
                destination,
                release_id="fixture-v1",
                seed=26,
                audit_report=audit,
                duplicate_groups={},
                leakage_violations=(),
            )

            config = yaml.safe_load((destination / "dataset.yaml").read_text())
            self.assertEqual(config["names"][0], "plastic_bottle")
            self.assertTrue(next((destination / "images" / "train").iterdir()).is_symlink())
            label = next((destination / "labels" / "train").iterdir()).read_text()
            self.assertEqual(label, "0 0.30000000 0.50000000 0.40000000 0.60000000\n")
            with self.assertRaises(FileExistsError):
                write_yolo_release(
                    [image],
                    {"fixture:1": "train"},
                    {"fixture": source},
                    destination,
                    release_id="fixture-v1",
                    seed=26,
                    audit_report=audit,
                    duplicate_groups={},
                    leakage_violations=(),
                )


if __name__ == "__main__":
    unittest.main()
