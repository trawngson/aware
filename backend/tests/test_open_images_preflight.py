from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from src.open_images_preflight import build_open_images_preflight


class OpenImagesPreflightTests(unittest.TestCase):
    def test_preflight_filters_classes_and_builds_deterministic_review(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            classes = root / "classes.csv"
            boxes = root / "boxes.csv"
            metadata = root / "metadata.csv"

            classes.write_text(
                "/m/bottle,Bottle\n"
                "/m/box,Box\n"
                "/m/bag,Plastic bag\n"
                "/m/can,Tin can\n"
                "/m/cat,Cat\n",
                encoding="utf-8",
            )
            with boxes.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=(
                        "ImageID",
                        "LabelName",
                        "XMin",
                        "XMax",
                        "YMin",
                        "YMax",
                        "IsGroupOf",
                        "IsDepiction",
                        "IsInside",
                    ),
                )
                writer.writeheader()
                writer.writerows(
                    [
                        {
                            "ImageID": "bag-real",
                            "LabelName": "/m/bag",
                            "XMin": "0.1",
                            "XMax": "0.5",
                            "YMin": "0.2",
                            "YMax": "0.8",
                            "IsGroupOf": "0",
                            "IsDepiction": "0",
                            "IsInside": "0",
                        },
                        {
                            "ImageID": "can-picture",
                            "LabelName": "/m/can",
                            "XMin": "0.2",
                            "XMax": "0.6",
                            "YMin": "0.1",
                            "YMax": "0.9",
                            "IsGroupOf": "0",
                            "IsDepiction": "1",
                            "IsInside": "0",
                        },
                        {
                            "ImageID": "cat",
                            "LabelName": "/m/cat",
                            "XMin": "0",
                            "XMax": "1",
                            "YMin": "0",
                            "YMax": "1",
                            "IsGroupOf": "0",
                            "IsDepiction": "0",
                            "IsInside": "0",
                        },
                    ]
                )
            with metadata.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=(
                        "ImageID",
                        "OriginalSize",
                        "Author",
                        "License",
                    ),
                )
                writer.writeheader()
                writer.writerows(
                    [
                        {
                            "ImageID": "bag-real",
                            "OriginalSize": "100",
                            "Author": "Bag Author",
                            "License": "https://creativecommons.org/licenses/by/2.0/",
                        },
                        {
                            "ImageID": "can-picture",
                            "OriginalSize": "200",
                            "Author": "Can Author",
                            "License": "https://creativecommons.org/licenses/by/2.0/",
                        },
                        {
                            "ImageID": "cat",
                            "OriginalSize": "300",
                            "Author": "Cat Author",
                            "License": "https://creativecommons.org/licenses/by/2.0/",
                        },
                    ]
                )

            report = build_open_images_preflight(
                class_descriptions_file=classes,
                boxes_file=boxes,
                image_metadata_file=metadata,
                destination=root / "first",
                sample_per_class=2,
                seed=26,
            )
            second = build_open_images_preflight(
                class_descriptions_file=classes,
                boxes_file=boxes,
                image_metadata_file=metadata,
                destination=root / "second",
                sample_per_class=2,
                seed=26,
            )

            self.assertEqual(
                report["box_counts"],
                {"Plastic bag": 1, "Tin can": 1},
            )
            self.assertEqual(report["selected_image_count"], 2)
            self.assertEqual(report["review_image_count"], 1)
            self.assertEqual(
                report["rejected_review_attributes"],
                {"IsDepiction": 1},
            )
            self.assertEqual(report["estimated_original_image_bytes"], 300)
            self.assertEqual(
                report["output_sha256"]["review-selection.csv"],
                second["output_sha256"]["review-selection.csv"],
            )


if __name__ == "__main__":
    unittest.main()
