from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from src.open_images_review import _render_tile


class OpenImagesReviewTests(unittest.TestCase):
    def test_review_tile_draws_normalized_box_without_changing_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            image_path = Path(temporary) / "sample.jpg"
            Image.new("RGB", (640, 480), "white").save(image_path)

            tile = _render_tile(
                image_path=image_path,
                image_id="abc",
                class_name="Plastic bag",
                boxes=[(0.25, 0.75, 0.25, 0.75)],
            )

            self.assertEqual(tile.size, (320, 272))
            red_pixels = 0
            for y in range(tile.height):
                for x in range(tile.width):
                    red, green, blue = tile.getpixel((x, y))
                    if red > 200 and green < 80 and blue < 80:
                        red_pixels += 1
            self.assertGreater(red_pixels, 100)


if __name__ == "__main__":
    unittest.main()
