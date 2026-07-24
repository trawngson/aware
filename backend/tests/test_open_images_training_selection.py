from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from src.open_images_training_selection import (
    select_open_images_training_metadata,
)


class OpenImagesTrainingSelectionTests(unittest.TestCase):
    def test_selects_only_approved_real_valid_boxes_with_attribution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            classes = root / "classes.csv"
            boxes = root / "boxes.csv"
            metadata = root / "metadata.csv"

            classes.write_text(
                "/m/bag,Plastic bag\n"
                "/m/can,Tin can\n"
                "/m/bottle,Bottle\n",
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
                            "ImageID": "bag",
                            "LabelName": "/m/bag",
                            "XMin": "0.1",
                            "XMax": "0.6",
                            "YMin": "0.2",
                            "YMax": "0.8",
                            "IsGroupOf": "0",
                            "IsDepiction": "0",
                            "IsInside": "0",
                        },
                        {
                            "ImageID": "depiction",
                            "LabelName": "/m/can",
                            "XMin": "0.1",
                            "XMax": "0.6",
                            "YMin": "0.2",
                            "YMax": "0.8",
                            "IsGroupOf": "0",
                            "IsDepiction": "1",
                            "IsInside": "0",
                        },
                        {
                            "ImageID": "can",
                            "LabelName": "/m/can",
                            "XMin": "0.2",
                            "XMax": "0.7",
                            "YMin": "0.1",
                            "YMax": "0.9",
                            "IsGroupOf": "0",
                            "IsDepiction": "0",
                            "IsInside": "0",
                        },
                        {
                            "ImageID": "invalid",
                            "LabelName": "/m/can",
                            "XMin": "0.7",
                            "XMax": "0.2",
                            "YMin": "0.2",
                            "YMax": "0.8",
                            "IsGroupOf": "0",
                            "IsDepiction": "0",
                            "IsInside": "0",
                        },
                        {
                            "ImageID": "bottle",
                            "LabelName": "/m/bottle",
                            "XMin": "0.1",
                            "XMax": "0.6",
                            "YMin": "0.2",
                            "YMax": "0.8",
                            "IsGroupOf": "0",
                            "IsDepiction": "0",
                            "IsInside": "0",
                        },
                        {
                            "ImageID": "no-author",
                            "LabelName": "/m/bag",
                            "XMin": "0.1",
                            "XMax": "0.6",
                            "YMin": "0.2",
                            "YMax": "0.8",
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
                            "ImageID": "bag",
                            "OriginalSize": "123",
                            "Author": "Bag Author",
                            "License": "https://creativecommons.org/licenses/by/2.0/",
                        },
                        {
                            "ImageID": "depiction",
                            "OriginalSize": "456",
                            "Author": "Can Author",
                            "License": "https://creativecommons.org/licenses/by/2.0/",
                        },
                        {
                            "ImageID": "can",
                            "OriginalSize": "456",
                            "Author": "Can Author",
                            "License": "https://creativecommons.org/licenses/by/2.0/",
                        },
                        {
                            "ImageID": "no-author",
                            "OriginalSize": "789",
                            "Author": "",
                            "License": "https://creativecommons.org/licenses/by/2.0/",
                        },
                    ]
                )

            report = select_open_images_training_metadata(
                class_descriptions_file=classes,
                boxes_file=boxes,
                image_metadata_file=metadata,
                destination=root / "selection",
                source_urls={"fixture": "https://example.invalid"},
            )

            self.assertEqual(
                report["selected_box_counts"],
                {"Plastic bag": 1, "Tin can": 1},
            )
            self.assertEqual(report["selected_unique_image_count"], 2)
            self.assertEqual(
                report["excluded_attribute_counts"],
                {"IsDepiction": 1},
            )
            self.assertEqual(report["invalid_box_counts"], {"Tin can": 1})
            self.assertEqual(report["estimated_original_bytes"], 579)
            self.assertEqual(
                report["attribution"]["rejected_counts"],
                {"missing_author": 1},
            )


if __name__ == "__main__":
    unittest.main()
