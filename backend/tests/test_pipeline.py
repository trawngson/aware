from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from src.adapters import adapt_open_images_csv, adapt_taco_coco
from src.audit import audit_canonical_images
from src.box_policy import minimum_size_review_reason, short_side_after_letterbox_resize
from src.canonical_data import CanonicalAnnotation, CanonicalImage, NormalizedBox
from src.dedup import difference_hash, exact_duplicate_groups, perceptual_duplicate_groups
from src.image_files import materialize_exif_oriented_copy
from src.mappings import MappingTable, validate_mapping_ledger
from src.metadata_validation import load_yaml_mapping
from src.splitting import assign_group_aware_splits, find_leakage


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = PROJECT_ROOT / "tests" / "fixtures"


def sample_image(
    image_id: str,
    *,
    group_id: str | None = None,
    exact_hash: str | None = None,
    box: NormalizedBox | None = None,
) -> CanonicalImage:
    annotation = CanonicalAnnotation(
        annotation_id=f"annotation-{image_id}",
        source_class="Clear plastic bottle",
        class_id=0,
        class_name="plastic_bottle",
        box=box or NormalizedBox(0.1, 0.1, 0.7, 0.9),
    )
    return CanonicalImage(
        image_id=image_id,
        source_id="fixture",
        source_version="v1",
        relative_path=f"images/{image_id}.jpg",
        width=640,
        height=480,
        group_id=group_id or image_id,
        exact_hash=exact_hash,
        annotations=(annotation,),
    )


class MappingAndAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ledger = load_yaml_mapping(PROJECT_ROOT / "mapping_ledger.yaml")
        fixture_ledger = copy.deepcopy(self.ledger)
        for entry in fixture_ledger["mappings"]:
            if entry["source_class"] in {"Clear plastic bottle", "Plastic bag"}:
                entry["review_status"] = "approved"
        self.mapping_table = MappingTable.from_document(fixture_ledger)

    def test_mapping_ledger_is_valid(self) -> None:
        result = validate_mapping_ledger(self.ledger)

        self.assertTrue(result.ok, result.render("mapping ledger"))

    def test_only_reviewed_taco_safe_mappings_are_approved(self) -> None:
        approved_taco = [
            entry
            for entry in self.ledger["mappings"]
            if entry["source"] == "taco-v1.0"
            and entry["action"] == "safe_merge"
            and entry["review_status"] == "approved"
        ]
        open_images_safe = [
            entry
            for entry in self.ledger["mappings"]
            if entry["source"] == "open-images-v7-waste-subset"
            and entry["action"] == "safe_merge"
        ]
        battery = next(
            entry
            for entry in self.ledger["mappings"]
            if entry["source"] == "taco-v1.0"
            and entry["source_class"] == "Battery"
        )

        self.assertEqual(len(approved_taco), 18)
        self.assertTrue(
            all(
                entry["review_status"] == "representative_samples_required"
                for entry in open_images_safe
            )
        )
        self.assertEqual(battery["action"], "reject")
        self.assertIsNone(battery["canonical_class"])

    def test_included_mapping_requires_a_canonical_class(self) -> None:
        changed = copy.deepcopy(self.ledger)
        changed["mappings"][0]["canonical_class"] = None

        result = validate_mapping_ledger(changed)

        self.assertFalse(result.ok)
        self.assertIn("required for included", result.render("mapping ledger"))

    def test_taco_adapter_preserves_source_label_and_exclusion(self) -> None:
        result = adapt_taco_coco(
            FIXTURES / "taco" / "annotations.json",
            mapping_table=self.mapping_table,
        )

        self.assertEqual(len(result.images), 1)
        annotation = result.images[0].annotations[0]
        self.assertEqual(annotation.source_class, "Clear plastic bottle")
        self.assertEqual(annotation.class_name, "plastic_bottle")
        self.assertEqual(annotation.box.as_yolo(), (0.3, 0.3, 0.4, 0.4))
        self.assertEqual(len(result.exclusions), 1)
        self.assertEqual(result.exclusions[0].action, "reject")

    def test_open_images_adapter_requires_attribution_and_excludes_ambiguous_label(self) -> None:
        result = adapt_open_images_csv(
            FIXTURES / "open_images" / "boxes.csv",
            FIXTURES / "open_images" / "classes.csv",
            FIXTURES / "open_images" / "images.csv",
            mapping_table=self.mapping_table,
        )

        self.assertEqual(len(result.images), 1)
        self.assertEqual(result.images[0].annotations[0].class_name, "plastic_bag")
        self.assertEqual(result.images[0].attribution["author"], "Fixture Author")
        self.assertEqual(len(result.exclusions), 1)
        self.assertEqual(result.exclusions[0].action, "manual_review")

    def test_training_view_size_policy_holds_tiny_boxes(self) -> None:
        tiny = NormalizedBox(0.1, 0.1, 0.11, 0.11)
        regular = NormalizedBox(0.1, 0.1, 0.3, 0.3)

        self.assertAlmostEqual(
            short_side_after_letterbox_resize(
                tiny,
                image_width=4000,
                image_height=3000,
            ),
            4.8,
        )
        self.assertIn(
            "below 12px",
            minimum_size_review_reason(
                tiny,
                class_name="plastic_bottle",
                image_width=4000,
                image_height=3000,
            )
            or "",
        )
        self.assertIsNone(
            minimum_size_review_reason(
                regular,
                class_name="plastic_bottle",
                image_width=4000,
                image_height=3000,
            )
        )

    def test_styrofoam_uses_stricter_twenty_pixel_minimum(self) -> None:
        box = NormalizedBox(0.1, 0.1, 0.13, 0.13)

        self.assertIsNone(
            minimum_size_review_reason(
                box,
                class_name="plastic_bottle",
                image_width=640,
                image_height=640,
            )
        )
        self.assertIn(
            "below 20px",
            minimum_size_review_reason(
                box,
                class_name="styrofoam",
                image_width=640,
                image_height=640,
            )
            or "",
        )


class AuditTests(unittest.TestCase):
    def test_invalid_box_is_reported(self) -> None:
        image = sample_image("bad", box=NormalizedBox(0.8, 0.2, 0.4, 0.7))

        report = audit_canonical_images([image])

        self.assertFalse(report.ok)
        self.assertIn("invalid_box", report.render())

    def test_missing_source_root_is_reported_without_creating_files(self) -> None:
        report = audit_canonical_images([sample_image("missing")], source_roots={})

        self.assertFalse(report.ok)
        self.assertIn("missing_source_root", report.render())

    def test_missing_image_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            report = audit_canonical_images(
                [sample_image("missing")],
                source_roots={"fixture": Path(temporary_directory)},
            )

        self.assertFalse(report.ok)
        self.assertIn("missing_image", report.render())

    def test_missing_required_class_is_reported(self) -> None:
        report = audit_canonical_images(
            [sample_image("only-bottle")],
            required_classes=("plastic_bottle", "styrofoam"),
        )

        self.assertFalse(report.ok)
        self.assertIn("missing_required_class", report.render())
        self.assertIn("styrofoam", report.render())

    def test_corrupt_image_is_reported_when_full_verification_is_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "images").mkdir()
            (root / "images" / "corrupt.jpg").write_bytes(b"not an image")
            image = sample_image("corrupt")
            report = audit_canonical_images(
                [image],
                source_roots={"fixture": root},
                verify_image_files=True,
            )

        self.assertFalse(report.ok)
        self.assertIn("corrupt_image", report.render())


class DeduplicationAndSplitTests(unittest.TestCase):
    def test_orientation_zero_is_preserved_without_derived_copy(self) -> None:
        from PIL import Image

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.png"
            destination = root / "derived.png"
            exif = Image.Exif()
            exif[274] = 0
            Image.new("RGB", (8, 12), "green").save(source, exif=exif)

            orientation = materialize_exif_oriented_copy(
                source,
                destination,
                expected_size=(8, 12),
            )

            self.assertEqual(orientation, 0)
            self.assertFalse(destination.exists())

    def test_orientation_three_creates_upright_derived_copy(self) -> None:
        from PIL import Image

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.png"
            destination = root / "derived.png"
            image = Image.new("RGB", (3, 2), "black")
            image.putpixel((2, 1), (255, 0, 0))
            exif = Image.Exif()
            exif[274] = 3
            image.save(source, exif=exif)

            orientation = materialize_exif_oriented_copy(
                source,
                destination,
                expected_size=(3, 2),
            )

            self.assertEqual(orientation, 3)
            with Image.open(destination) as derived:
                self.assertEqual(derived.getexif().get(274, 1), 1)
                self.assertEqual(derived.getpixel((0, 0)), (255, 0, 0))

    def test_perceptual_hash_uses_visual_exif_orientation(self) -> None:
        from PIL import Image

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            portrait = Image.new("L", (8, 16))
            for y in range(16):
                for x in range(8):
                    portrait.putpixel((x, y), (x * 31 + y * 7) % 256)
            upright_path = root / "upright.png"
            portrait.save(upright_path)

            stored_sideways = portrait.transpose(Image.Transpose.ROTATE_90)
            exif = Image.Exif()
            exif[274] = 6
            sideways_path = root / "sideways.png"
            stored_sideways.save(sideways_path, exif=exif)

            self.assertEqual(
                difference_hash(upright_path),
                difference_hash(sideways_path),
            )

    def test_exact_and_perceptual_duplicate_groups(self) -> None:
        exact = exact_duplicate_groups({"a": "one", "b": "one", "c": "two"})
        perceptual = perceptual_duplicate_groups(
            {"a": "0000000000000000", "b": "0000000000000001", "c": "ffffffffffffffff"},
            maximum_distance=1,
        )

        self.assertEqual(exact["a"], exact["b"])
        self.assertNotIn("c", exact)
        self.assertEqual(perceptual["a"], perceptual["b"])
        self.assertNotIn("c", perceptual)

    def test_group_aware_split_is_deterministic_and_keeps_duplicates_together(self) -> None:
        images = [
            sample_image("a", group_id="session-1"),
            sample_image("b", group_id="session-1"),
            sample_image("c", exact_hash="same"),
            sample_image("d", exact_hash="same"),
            sample_image("e"),
        ]
        duplicate_groups = {"b": "near-1", "e": "near-1"}

        first = assign_group_aware_splits(images, seed=26, duplicate_groups=duplicate_groups)
        second = assign_group_aware_splits(images, seed=26, duplicate_groups=duplicate_groups)

        self.assertEqual(first, second)
        self.assertEqual(first["a"], first["b"])
        self.assertEqual(first["c"], first["d"])
        self.assertEqual(first["b"], first["e"])
        self.assertEqual(find_leakage(images, first, duplicate_groups=duplicate_groups), ())

    def test_leakage_verifier_detects_cross_split_exact_duplicate(self) -> None:
        images = [
            sample_image("a", exact_hash="same"),
            sample_image("b", exact_hash="same"),
        ]

        violations = find_leakage(images, {"a": "train", "b": "val"})

        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].relationship, "exact_hash")


if __name__ == "__main__":
    unittest.main()
