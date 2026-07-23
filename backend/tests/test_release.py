from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml
from PIL import Image

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
            Image.new("RGB", (100, 100), "white").save(image_file)
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

    def test_release_normalizes_exif_orientation_without_changing_raw_image(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            source.mkdir()
            image_file = source / "portrait.jpg"
            exif = Image.Exif()
            exif[274] = 6
            Image.new("RGB", (40, 20), "blue").save(image_file, exif=exif)
            image = CanonicalImage(
                image_id="fixture:portrait",
                source_id="fixture",
                source_version="v1",
                relative_path="portrait.jpg",
                width=20,
                height=40,
                group_id="capture-portrait",
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
            audit = audit_canonical_images(
                [image],
                source_roots={"fixture": source},
                verify_image_files=True,
            )
            self.assertTrue(audit.ok, audit.render())

            destination = root / "release"
            write_yolo_release(
                [image],
                {"fixture:portrait": "train"},
                {"fixture": source},
                destination,
                release_id="fixture-oriented-v1",
                seed=26,
                audit_report=audit,
                duplicate_groups={},
                leakage_violations=(),
            )

            released = next((destination / "images" / "train").iterdir())
            self.assertFalse(released.is_symlink())
            with Image.open(released) as opened:
                self.assertEqual(opened.size, (20, 40))
                self.assertEqual(opened.getexif().get(274, 1), 1)
            with Image.open(image_file) as opened:
                self.assertEqual(opened.size, (40, 20))
                self.assertEqual(opened.getexif().get(274), 6)

            manifest_line = (
                destination / "manifests" / "canonical_images.jsonl"
            ).read_text(encoding="utf-8")
            record = json.loads(manifest_line)
            self.assertEqual(
                record["release_image"],
                {
                    "mode": "derived_copy",
                    "exif_transposed": True,
                    "source_exif_orientation": 6,
                },
            )

    def test_release_records_nonstandard_orientation_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            source.mkdir()
            image_file = source / "orientation-zero.png"
            exif = Image.Exif()
            exif[274] = 0
            Image.new("RGB", (20, 30), "green").save(image_file, exif=exif)
            image = CanonicalImage(
                image_id="fixture:orientation-zero",
                source_id="fixture",
                source_version="v1",
                relative_path="orientation-zero.png",
                width=20,
                height=30,
                group_id="capture-orientation-zero",
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
            audit = audit_canonical_images(
                [image],
                source_roots={"fixture": source},
                verify_image_files=True,
            )
            destination = root / "release"

            write_yolo_release(
                [image],
                {"fixture:orientation-zero": "train"},
                {"fixture": source},
                destination,
                release_id="fixture-orientation-zero-v1",
                seed=26,
                audit_report=audit,
                duplicate_groups={},
                leakage_violations=(),
            )

            released = next((destination / "images" / "train").iterdir())
            self.assertTrue(released.is_symlink())
            record = json.loads(
                (destination / "manifests" / "canonical_images.jsonl").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                record["release_image"],
                {
                    "mode": "raw_symlink",
                    "exif_transposed": False,
                    "source_exif_orientation": 0,
                },
            )


if __name__ == "__main__":
    unittest.main()
