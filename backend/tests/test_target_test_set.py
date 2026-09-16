from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from src.metadata_validation import EXPECTED_CLASSES
from src.project_paths import PathConfigurationError, ProjectPaths
from src.target_test_set import (
    ClassOrderError,
    TargetTestSetError,
    ingest_target_test_set,
    load_ontology_class_names,
    read_frozen_class_order,
    resolve_class_order,
    verify_frozen_test_manifest,
    write_frozen_test_manifest,
)


BACKEND_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_NAME = "target_test_set"
FIXTURE_ROOT = BACKEND_ROOT / "tests" / "fixtures" / FIXTURE_NAME

# The order the fixture's labeler loaded into MakeSense. It is deliberately a
# three-cycle away from the frozen ontology order so that a test can tell the
# correct mapping (exported id -> name -> canonical id) apart from its inverse.
FIXTURE_CLASS_ORDER = (
    "metal_can",        # exported 0 -> canonical 2
    "plastic_bottle",   # exported 1 -> canonical 0
    "cardboard",        # exported 2 -> canonical 3
    "glass_container",  # exported 3 -> canonical 1
    "plastic_bag",      # exported 4 -> canonical 4
    "disposable_cup",   # exported 5 -> canonical 5
    "styrofoam",        # exported 6 -> canonical 6
)
FIXTURE_IMAGE_COUNT = 3


class TargetTestSetHarness(unittest.TestCase):
    """Builds ProjectPaths whose data and output roots are both disposable."""

    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.temporary_root = Path(self._temporary.name)
        self.data_root = self.temporary_root / "data"
        self.data_root.mkdir()
        self.output_root = self.temporary_root / "outputs"
        shutil.copytree(FIXTURE_ROOT, self.data_root / FIXTURE_NAME)
        self.paths = ProjectPaths.from_environment(
            project_root=BACKEND_ROOT,
            environ={
                "PROJECT_DATA_ROOT": str(self.data_root),
                "PROJECT_OUTPUT_ROOT": str(self.output_root),
            },
        )

    @property
    def fixture(self) -> Path:
        return self.data_root / FIXTURE_NAME

    def ingest(self, **overrides):
        arguments = {
            "class_order": FIXTURE_CLASS_ORDER,
            "accepted_list_path": self.fixture / "accepted_images.txt",
            "labels_root": self.fixture / "labels",
            "image_roots": {
                1: self.fixture / "images" / "Session 1",
                2: self.fixture / "images" / "Session 2",
            },
            "expected_image_count": FIXTURE_IMAGE_COUNT,
        }
        arguments.update(overrides)
        return ingest_target_test_set(self.paths, **arguments)

    def freeze(self, report, *, directory: str = "target_test/v1"):
        return write_frozen_test_manifest(
            report,
            self.output_root / directory,
            paths=self.paths,
            manifest_id="aware-smartphone-test-v1-frozen",
            frozen_on="2026-09-16",
        )

    def boxes_by_stem(self, report) -> dict[str, list[tuple[int, str]]]:
        return {
            image.image_id.rsplit(":", 1)[1]: [
                (annotation.class_id, annotation.class_name)
                for annotation in image.annotations
            ]
            for image in report.images
        }


class OntologyClassOrderTests(TargetTestSetHarness):
    def test_class_names_come_from_the_ontology_file(self) -> None:
        names = load_ontology_class_names(BACKEND_ROOT / "ontology.yaml")

        # Guards against a second hardcoded copy of the class list drifting
        # away from the frozen ontology.
        self.assertEqual(names, EXPECTED_CLASSES)

    def test_class_order_argument_is_required(self) -> None:
        with self.assertRaises(TypeError):
            ingest_target_test_set(  # type: ignore[call-arg]
                self.paths,
                accepted_list_path=self.fixture / "accepted_images.txt",
                labels_root=self.fixture / "labels",
                image_roots={1: self.fixture / "images" / "Session 1"},
                expected_image_count=FIXTURE_IMAGE_COUNT,
            )

    def test_explicit_none_class_order_is_refused(self) -> None:
        with self.assertRaises(ClassOrderError) as captured:
            self.ingest(class_order=None)

        self.assertIn("cannot be defaulted", str(captured.exception))

    def test_class_order_must_be_a_permutation_of_the_ontology(self) -> None:
        with self.assertRaises(ClassOrderError) as captured:
            self.ingest(
                class_order=(
                    "metal_can",
                    "plastic_bottle",
                    "cardboard",
                    "glass_container",
                    "plastic_bag",
                    "disposable_cup",
                    "aluminium_foil",  # not an ontology class
                )
            )

        message = str(captured.exception)
        self.assertIn("permutation", message)
        self.assertIn("aluminium_foil", message)
        self.assertIn("styrofoam", message)

    def test_class_order_of_the_wrong_length_is_refused(self) -> None:
        with self.assertRaises(ClassOrderError) as captured:
            self.ingest(class_order=FIXTURE_CLASS_ORDER[:-1])

        self.assertIn("exactly 7 classes", str(captured.exception))

    def test_class_order_with_repeats_is_refused(self) -> None:
        duplicated = ("metal_can",) + FIXTURE_CLASS_ORDER[1:-1] + ("metal_can",)

        with self.assertRaises(ClassOrderError) as captured:
            self.ingest(class_order=duplicated)

        self.assertIn("repeats", str(captured.exception))

    def test_a_permutation_in_a_different_order_is_accepted(self) -> None:
        report = self.ingest(class_order=tuple(reversed(EXPECTED_CLASSES)))

        self.assertTrue(report.ok, report.render())

    def test_resolve_class_order_maps_names_to_canonical_ids(self) -> None:
        mapping = resolve_class_order(FIXTURE_CLASS_ORDER, EXPECTED_CLASSES)

        self.assertEqual(mapping["metal_can"], 2)
        self.assertEqual(mapping["plastic_bottle"], 0)
        self.assertEqual(mapping["cardboard"], 3)


class IngestHappyPathTests(TargetTestSetHarness):
    def test_happy_path_produces_a_clean_report(self) -> None:
        report = self.ingest()

        self.assertTrue(report.ok, report.render())
        self.assertEqual(report.exclusions, ())
        self.assertEqual(report.accepted_without_labels, ())
        self.assertEqual(report.labels_without_accepted_image, ())
        self.assertEqual(len(report.images), FIXTURE_IMAGE_COUNT)
        self.assertEqual(report.box_count, 4)
        self.assertEqual(report.recorded_class_order, FIXTURE_CLASS_ORDER)
        self.assertEqual(report.ontology_version, "aware-ontology-v3")

    def test_exported_ids_map_through_the_recorded_order_not_its_inverse(self) -> None:
        # Exported 0 is metal_can for this labeler, so the canonical ID is 2.
        # Reading the mapping backwards would yield 1 (plastic_bottle's position
        # in the recorded order), so this assertion pins the direction.
        report = self.ingest()

        boxes = self.boxes_by_stem(report)
        self.assertEqual(boxes["IMG_0001"], [(2, "metal_can")])
        self.assertEqual(
            boxes["IMG_0002"], [(3, "cardboard"), (1, "glass_container")]
        )
        self.assertEqual(boxes["IMG_0003"], [(0, "plastic_bottle")])

    def test_multi_box_image_keeps_every_box(self) -> None:
        report = self.ingest()

        multi = next(
            image for image in report.images if image.image_id.endswith("IMG_0002")
        )
        self.assertEqual(len(multi.annotations), 2)
        self.assertEqual(
            {annotation.annotation_id for annotation in multi.annotations},
            {f"{multi.image_id}#1", f"{multi.image_id}#2"},
        )

    def test_final_label_line_has_no_trailing_newline(self) -> None:
        for relative in (
            "labels/batch_01/IMG_0001.txt",
            "labels/batch_01/IMG_0002.txt",
            "labels/batch_02/IMG_0003.txt",
        ):
            content = (FIXTURE_ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertTrue(content)
                self.assertNotEqual(content[-1], "\n")

        # The two-line file genuinely has two boxes despite the missing newline.
        report = self.ingest()
        self.assertEqual(report.box_count, 4)

    def test_capture_session_and_image_evidence_are_recorded(self) -> None:
        report = self.ingest()

        sessions = {image.image_id: image.group_id for image in report.images}
        self.assertEqual(
            set(sessions.values()), {"session-1", "session-2"}
        )
        for image in report.images:
            with self.subTest(image=image.image_id):
                self.assertEqual(len(image.exact_hash or ""), 64)
                self.assertGreater(image.width, 0)
                self.assertGreater(image.height, 0)
                self.assertFalse(Path(image.relative_path).is_absolute())

    def test_expected_image_count_is_a_parameter_and_is_enforced(self) -> None:
        with self.assertRaises(TargetTestSetError) as captured:
            self.ingest(expected_image_count=119)

        self.assertIn("expected 119", str(captured.exception))


class IngestFailClosedTests(TargetTestSetHarness):
    def test_unknown_exported_class_id_is_excluded(self) -> None:
        (self.fixture / "labels/batch_02/IMG_0003.txt").write_text(
            "9 0.400000 0.550000 0.480000 0.500000", encoding="utf-8"
        )

        report = self.ingest()

        self.assertFalse(report.ok)
        actions = {item.action for item in report.exclusions}
        self.assertEqual(actions, {"invalid_label_file"})
        self.assertIn("outside 0-6", report.exclusions[0].reason)
        # Fail closed: the bad image is not silently included.
        self.assertEqual(len(report.images), FIXTURE_IMAGE_COUNT - 1)
        with self.assertRaises(TargetTestSetError):
            self.freeze(report)

    def test_negative_exported_class_id_is_excluded(self) -> None:
        (self.fixture / "labels/batch_02/IMG_0003.txt").write_text(
            "-1 0.400000 0.550000 0.480000 0.500000", encoding="utf-8"
        )

        report = self.ingest()

        self.assertFalse(report.ok)
        self.assertIn("outside 0-6", report.exclusions[0].reason)

    def test_out_of_bounds_box_is_excluded(self) -> None:
        # xmax = 0.95 + 0.30 / 2 = 1.10, which leaves the image.
        (self.fixture / "labels/batch_01/IMG_0001.txt").write_text(
            "0 0.950000 0.480000 0.300000 0.420000", encoding="utf-8"
        )

        report = self.ingest()

        self.assertFalse(report.ok)
        self.assertEqual(report.exclusions[0].action, "invalid_label_file")
        self.assertIn("within [0, 1]", report.exclusions[0].reason)
        with self.assertRaises(TargetTestSetError):
            self.freeze(report)

    def test_zero_area_box_is_excluded(self) -> None:
        (self.fixture / "labels/batch_01/IMG_0001.txt").write_text(
            "0 0.500000 0.480000 0.000000 0.420000", encoding="utf-8"
        )

        report = self.ingest()

        self.assertFalse(report.ok)
        self.assertIn("positive width and height", report.exclusions[0].reason)

    def test_malformed_label_line_is_excluded(self) -> None:
        (self.fixture / "labels/batch_01/IMG_0001.txt").write_text(
            "0 0.5 0.48 0.3", encoding="utf-8"
        )

        report = self.ingest()

        self.assertFalse(report.ok)
        self.assertIn("expected 5 fields", report.exclusions[0].reason)

    def test_every_bad_line_in_a_file_is_reported(self) -> None:
        (self.fixture / "labels/batch_01/IMG_0002.txt").write_text(
            "9 0.250000 0.300000 0.200000 0.240000\n"
            "3 0.950000 0.660000 0.360000 0.300000",
            encoding="utf-8",
        )

        report = self.ingest()

        self.assertFalse(report.ok)
        reason = report.exclusions[0].reason
        self.assertIn("line 1", reason)
        self.assertIn("line 2", reason)

    def test_empty_label_file_is_excluded(self) -> None:
        (self.fixture / "labels/batch_01/IMG_0001.txt").write_text(
            "", encoding="utf-8"
        )

        report = self.ingest()

        self.assertFalse(report.ok)
        self.assertIn("empty", report.exclusions[0].reason)

    def test_accepted_image_without_a_label_is_reported_and_blocks_freeze(self) -> None:
        (self.fixture / "labels/batch_02/IMG_0003.txt").unlink()

        report = self.ingest()

        self.assertFalse(report.ok)
        self.assertEqual(report.accepted_without_labels, ("IMG_0003",))
        self.assertEqual(report.exclusions[0].action, "missing_label_file")
        self.assertEqual(len(report.images), FIXTURE_IMAGE_COUNT - 1)
        with self.assertRaises(TargetTestSetError):
            self.freeze(report)

    def test_label_without_an_accepted_image_is_reported_and_blocks_freeze(self) -> None:
        (self.fixture / "labels/batch_02/IMG_9999.txt").write_text(
            "0 0.400000 0.550000 0.480000 0.500000", encoding="utf-8"
        )

        report = self.ingest()

        self.assertFalse(report.ok)
        self.assertEqual(report.labels_without_accepted_image, ("IMG_9999",))
        self.assertEqual(
            [item.action for item in report.exclusions], ["unmatched_label_file"]
        )
        # The approved images themselves still parsed; nothing is silently lost.
        self.assertEqual(len(report.images), FIXTURE_IMAGE_COUNT)
        with self.assertRaises(TargetTestSetError):
            self.freeze(report)

    def test_missing_image_file_is_excluded(self) -> None:
        (self.fixture / "images/Session 2/IMG_0003.png").unlink()

        report = self.ingest()

        self.assertFalse(report.ok)
        self.assertEqual(report.exclusions[0].action, "missing_image_file")

    def test_undecodable_image_is_excluded(self) -> None:
        (self.fixture / "images/Session 2/IMG_0003.png").write_bytes(
            b"not a real png"
        )

        report = self.ingest()

        self.assertFalse(report.ok)
        self.assertEqual(report.exclusions[0].action, "unreadable_image_file")
        with self.assertRaises(TargetTestSetError):
            self.freeze(report)

    def test_duplicate_label_stems_across_batches_are_refused(self) -> None:
        shutil.copyfile(
            self.fixture / "labels/batch_01/IMG_0001.txt",
            self.fixture / "labels/batch_02/IMG_0001.txt",
        )

        with self.assertRaises(TargetTestSetError) as captured:
            self.ingest()

        self.assertIn("more than once", str(captured.exception))

    def test_stray_classes_txt_is_refused_as_non_authoritative(self) -> None:
        (self.fixture / "labels/classes.txt").write_text(
            "plastic_bottle\nmetal_can\n", encoding="utf-8"
        )

        with self.assertRaises(TargetTestSetError) as captured:
            self.ingest()

        message = str(captured.exception)
        self.assertIn("not treated as authoritative", message)
        # Its contents are surfaced so a human can reconcile them, and the file
        # is kept rather than deleted.
        self.assertIn("plastic_bottle, metal_can", message)
        self.assertTrue((self.fixture / "labels/classes.txt").is_file())

    def test_a_wholly_missing_export_reports_every_accepted_image(self) -> None:
        for label in self.fixture.glob("labels/*/*.txt"):
            label.unlink()

        report = self.ingest()

        self.assertFalse(report.ok)
        self.assertEqual(
            report.accepted_without_labels, ("IMG_0001", "IMG_0002", "IMG_0003")
        )
        self.assertEqual(
            [item.action for item in report.exclusions],
            ["missing_label_file"] * FIXTURE_IMAGE_COUNT,
        )
        self.assertEqual(report.images, ())
        with self.assertRaises(TargetTestSetError):
            self.freeze(report)

    def test_input_paths_outside_the_data_root_are_refused(self) -> None:
        outside = self.temporary_root / "elsewhere" / "accepted_images.txt"
        outside.parent.mkdir()
        outside.write_text("1. /Session 1/IMG_0001.png\n", encoding="utf-8")

        with self.assertRaises(PathConfigurationError):
            self.ingest(accepted_list_path=outside)


class FrozenManifestTests(TargetTestSetHarness):
    def test_manifest_is_checksummed_and_records_the_class_order(self) -> None:
        manifest_path = self.freeze(self.ingest())
        document = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(document["recorded_class_order"], list(FIXTURE_CLASS_ORDER))
        self.assertEqual(document["ontology_class_names"], list(EXPECTED_CLASSES))
        self.assertEqual(document["class_order_to_canonical_id"]["metal_can"], 2)
        self.assertEqual(document["counts"]["images"], FIXTURE_IMAGE_COUNT)
        self.assertEqual(document["counts"]["boxes"], 4)
        self.assertEqual(
            document["counts"]["images_by_capture_session"],
            {"session-1": 2, "session-2": 1},
        )
        self.assertEqual(len(document["manifest_checksum"]), 64)
        self.assertEqual(verify_frozen_test_manifest(manifest_path), ())
        self.assertEqual(
            read_frozen_class_order(manifest_path), FIXTURE_CLASS_ORDER
        )

    def test_manifest_records_per_image_evidence(self) -> None:
        manifest_path = self.freeze(self.ingest())
        document = json.loads(manifest_path.read_text(encoding="utf-8"))

        by_id = {image["image_id"]: image for image in document["images"]}
        entry = by_id["aware-smartphone-test-v1:session-1:IMG_0002"]
        self.assertEqual(entry["capture_session"], "session-1")
        self.assertEqual((entry["width"], entry["height"]), (32, 24))
        self.assertEqual(len(entry["sha256"]), 64)
        self.assertEqual(
            [box["canonical_class_id"] for box in entry["boxes"]], [3, 1]
        )
        self.assertEqual(
            [box["exported_class"] for box in entry["boxes"]],
            ["makesense_class_2", "makesense_class_3"],
        )

    def test_manifest_holds_no_absolute_paths(self) -> None:
        manifest_path = self.freeze(self.ingest())
        raw = manifest_path.read_text(encoding="utf-8")

        self.assertNotIn(str(self.data_root), raw)
        self.assertNotIn(str(BACKEND_ROOT), raw)

    def test_refuses_to_overwrite_an_existing_frozen_manifest(self) -> None:
        first = self.freeze(self.ingest())
        original = first.read_text(encoding="utf-8")

        with self.assertRaises(FileExistsError):
            self.freeze(self.ingest())

        self.assertEqual(first.read_text(encoding="utf-8"), original)

    def test_freezing_is_deterministic_for_the_same_inputs(self) -> None:
        first = self.freeze(self.ingest(), directory="target_test/a")
        second = self.freeze(self.ingest(), directory="target_test/b")

        self.assertEqual(
            json.loads(first.read_text(encoding="utf-8"))["manifest_checksum"],
            json.loads(second.read_text(encoding="utf-8"))["manifest_checksum"],
        )

    def test_verify_detects_an_edited_manifest(self) -> None:
        manifest_path = self.freeze(self.ingest())
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
        document["images"][0]["boxes"][0]["canonical_class_id"] = 5
        manifest_path.write_text(json.dumps(document), encoding="utf-8")

        problems = verify_frozen_test_manifest(manifest_path)

        self.assertEqual(len(problems), 1)
        self.assertIn("checksum mismatch", problems[0])

    def test_verify_detects_changed_image_bytes_and_dimensions(self) -> None:
        manifest_path = self.freeze(self.ingest())
        replaced = self.fixture / "images/Session 1/IMG_0002.png"
        Image.new("RGB", (40, 30), (1, 2, 3)).save(replaced, format="PNG")

        problems = verify_frozen_test_manifest(
            manifest_path, data_root=self.data_root
        )

        self.assertTrue(any("image bytes changed" in item for item in problems))
        self.assertTrue(any("dimension mismatch" in item for item in problems))

    def test_verify_detects_a_missing_frozen_image(self) -> None:
        manifest_path = self.freeze(self.ingest())
        (self.fixture / "images/Session 2/IMG_0003.png").unlink()

        problems = verify_frozen_test_manifest(
            manifest_path, data_root=self.data_root
        )

        self.assertTrue(any("frozen image file is absent" in item for item in problems))

    def test_destination_outside_the_output_root_is_refused(self) -> None:
        with self.assertRaises(PathConfigurationError):
            write_frozen_test_manifest(
                self.ingest(),
                self.temporary_root / "elsewhere",
                paths=self.paths,
                manifest_id="aware-smartphone-test-v1-frozen",
                frozen_on="2026-09-16",
            )


if __name__ == "__main__":
    unittest.main()
