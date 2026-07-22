from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.inventory import inventory_approved_sources, inventory_source
from src.metadata_validation import load_yaml_mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class InventoryTests(unittest.TestCase):
    def test_missing_source_is_reported_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            missing = Path(temporary_directory) / "missing"
            inventory = inventory_source("fixture", missing)

            self.assertEqual(inventory.path_status, "missing")
            self.assertFalse(missing.exists())

    def test_manifest_path_escape_is_rejected(self) -> None:
        manifest = load_yaml_mapping(PROJECT_ROOT / "source_manifest.yaml")
        manifest["sources"][0]["acquisition"]["raw_subdirectory"] = "../escape"

        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaises(ValueError):
                inventory_approved_sources(temporary_directory, manifest)


if __name__ == "__main__":
    unittest.main()
