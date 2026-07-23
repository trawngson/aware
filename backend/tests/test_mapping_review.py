from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from src.mapping_review import render_review_sheets, select_review_samples


class MappingReviewTests(unittest.TestCase):
    def test_selection_is_deterministic_and_order_independent(self) -> None:
        document = {
            "categories": [{"id": 1, "name": "Bottle"}],
            "images": [
                {"id": 1, "file_name": "one.png"},
                {"id": 2, "file_name": "two.png"},
                {"id": 3, "file_name": "three.png"},
            ],
            "annotations": [
                {"id": 10, "image_id": 1, "category_id": 1, "bbox": [1, 2, 3, 4]},
                {"id": 11, "image_id": 2, "category_id": 1, "bbox": [2, 3, 4, 5]},
                {"id": 12, "image_id": 3, "category_id": 1, "bbox": [3, 4, 5, 6]},
            ],
        }
        reversed_document = {**document, "annotations": list(reversed(document["annotations"]))}

        first = select_review_samples(
            document,
            ["Bottle"],
            seed=26,
            samples_per_class=2,
        )
        second = select_review_samples(
            reversed_document,
            ["Bottle"],
            seed=26,
            samples_per_class=2,
        )

        self.assertEqual(first, second)
        self.assertEqual(len(first["Bottle"]), 2)

    def test_renderer_applies_exif_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            images = root / "images"
            images.mkdir()
            source = images / "oriented.png"
            exif = Image.Exif()
            exif[274] = 6
            Image.new("RGB", (40, 20), "blue").save(source, exif=exif)
            document = {
                "categories": [{"id": 1, "name": "Bottle"}],
                "images": [{"id": 1, "file_name": "oriented.png"}],
                "annotations": [
                    {"id": 10, "image_id": 1, "category_id": 1, "bbox": [2, 4, 10, 12]}
                ],
            }
            samples = select_review_samples(
                document,
                ["Bottle"],
                seed=26,
                samples_per_class=12,
            )
            destination = root / "review"

            rendered = render_review_sheets(samples, images, destination)

            self.assertEqual(len(rendered), 1)
            self.assertTrue(rendered[0].is_file())
            self.assertTrue((destination / "index.html").is_file())
            self.assertTrue((destination / "complete-review.jpg").is_file())
            with self.assertRaises(FileExistsError):
                render_review_sheets(samples, images, destination)


if __name__ == "__main__":
    unittest.main()
