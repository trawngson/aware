"""Ingest the MakeSense-labeled smartphone target-domain test set and freeze it.

The target-domain test set is evaluation-only (``SPECIFICATION.md`` sections 7
and 10) and must be frozen before model comparison so that Phase 9 and Phase 10
can keep it identical across experiments. This module turns the returned
MakeSense YOLO export into an immutable, checksummed manifest.

Class order is an input, not a constant
---------------------------------------
A MakeSense YOLO export contains only bare integer class IDs. It ships no
``classes.txt``, so the integer-to-name correspondence exists *only* in the
order the human labeler loaded the class list into the tool and cannot be
recovered from the label files. A silently wrong order produces labels that
pass every bounds check and every checksum while every class is wrong.

Therefore :func:`ingest_target_test_set` takes ``class_order`` as a required
keyword-only argument with no default, validates that it is exactly a
permutation of the frozen ontology names, records it verbatim in the manifest,
and refuses to guess. The mapping direction is::

    name = class_order[exported_class_id]     # labeler's list
    canonical_id = ontology_index[name]       # frozen ontology.yaml order

Fail-closed policy
------------------
Every problem is recorded as an explicit :class:`ExclusionEvent`; nothing is
ever silently dropped. Any exclusion, and any audit error, blocks the freeze.
This deliberately includes the two "reporting" conditions:

* an accepted image with no label file, and
* a label file with no accepted image.

Both are ambiguous (genuinely empty scene versus missing or misfiled work), and
a frozen evaluation manifest with unexplained gaps is worse than a refusal. The
operator must resolve them and re-run rather than freeze a partial test set.

The module never writes to the source data and never touches the network.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .audit import DatasetAuditReport, audit_canonical_images
from .canonical_data import (
    CanonicalAnnotation,
    CanonicalImage,
    ExclusionEvent,
    NormalizedBox,
)
from .dedup import sha256_file
from .image_files import visually_oriented_size
from .metadata_validation import load_yaml_mapping
from .project_paths import ProjectPaths, require_path_within


MANIFEST_SCHEMA_VERSION = "1.0"
TARGET_TEST_SOURCE_ID = "aware-smartphone-test-v1"
MANIFEST_FILENAME = "target_test_manifest.json"

#: ``N. /Session S/FILENAME`` lines in the approved accepted-image list.
ACCEPTED_PATTERN = re.compile(r"^(\d+)\.\s+/Session\s+(\d+)/(\S.*)$")

#: Export members that macOS archive tooling adds and that carry no labels.
IGNORED_LABEL_NAMES = ("__MACOSX",)


class TargetTestSetError(RuntimeError):
    """Raised when the target test set cannot be ingested or frozen."""


class ClassOrderError(TargetTestSetError):
    """Raised when the supplied labeling class order is missing or invalid."""


@dataclass(frozen=True)
class AcceptedImage:
    """One image approved for annotation, as listed by the supervisor."""

    number: int
    session: int
    filename: str

    @property
    def stem(self) -> str:
        return Path(self.filename).stem


@dataclass(frozen=True)
class TargetTestIngestReport:
    """Everything learned about the returned labels, before any freeze."""

    source_id: str
    source_version: str
    ontology_version: str
    ontology_class_names: tuple[str, ...]
    recorded_class_order: tuple[str, ...]
    class_order_to_canonical_id: dict[str, int]
    images: tuple[CanonicalImage, ...]
    exclusions: tuple[ExclusionEvent, ...]
    audit: DatasetAuditReport
    accepted_without_labels: tuple[str, ...]
    labels_without_accepted_image: tuple[str, ...]
    accepted_list_relative_path: str
    accepted_list_sha256: str
    expected_image_count: int
    accepted_image_count: int

    @property
    def ok(self) -> bool:
        """True only when nothing was excluded and the audit found no errors."""

        return not self.exclusions and self.audit.ok

    @property
    def box_count(self) -> int:
        return sum(len(image.annotations) for image in self.images)

    def render(self) -> str:
        lines = [
            f"target test ingest: {'PASS' if self.ok else 'FAIL'}",
            f"images: {len(self.images)} (expected {self.expected_image_count})",
            f"boxes: {self.box_count}",
            f"recorded class order: {list(self.recorded_class_order)}",
        ]
        if self.accepted_without_labels:
            lines.append(
                "accepted images with no label file: "
                f"{list(self.accepted_without_labels)}"
            )
        if self.labels_without_accepted_image:
            lines.append(
                "label files with no accepted image: "
                f"{list(self.labels_without_accepted_image)}"
            )
        for exclusion in self.exclusions:
            lines.append(
                f"[EXCLUDED] {exclusion.action} {exclusion.image_id}: {exclusion.reason}"
            )
        lines.append(self.audit.render())
        return "\n".join(lines)


def _canonical_json(document: Mapping[str, Any]) -> str:
    """Serialize deterministically so writer and verifier cannot drift."""

    return json.dumps(document, sort_keys=True, separators=(",", ":"))


def _checksum_of(document: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(document).encode("utf-8")).hexdigest()


def load_ontology_class_names(ontology_path: str | Path) -> tuple[str, ...]:
    """Return the frozen canonical class names in numeric-ID order.

    The names come from ``ontology.yaml`` through the existing loader so that
    this module never keeps a second copy of the class list.
    """

    document = load_yaml_mapping(ontology_path)
    classes = document.get("classes")
    if not isinstance(classes, list) or not classes:
        raise TargetTestSetError(f"{ontology_path} has no class list")
    by_id: dict[int, str] = {}
    for entry in classes:
        if not isinstance(entry, Mapping):
            raise TargetTestSetError(f"{ontology_path} has a malformed class entry")
        class_id = entry.get("id")
        name = entry.get("name")
        if not isinstance(class_id, int) or not isinstance(name, str) or not name:
            raise TargetTestSetError(f"{ontology_path} has a class without an id or name")
        if class_id in by_id:
            raise TargetTestSetError(f"{ontology_path} repeats class id {class_id}")
        by_id[class_id] = name
    if sorted(by_id) != list(range(len(by_id))):
        raise TargetTestSetError(
            f"{ontology_path} class ids must be contiguous from zero"
        )
    return tuple(by_id[index] for index in range(len(by_id)))


def resolve_class_order(
    class_order: Sequence[str] | None,
    ontology_class_names: Sequence[str],
) -> dict[str, int]:
    """Validate the labeler's class list and map each name to its canonical ID.

    ``class_order`` must be exactly a permutation of the frozen ontology names:
    same length, same members, no repeats. Order may differ, because the order
    is the labeler's, and that is precisely the information the export lost.
    """

    if class_order is None:
        raise ClassOrderError(
            "class_order is required: a MakeSense export carries no class names, "
            "so the labeling order must be supplied explicitly and cannot be "
            "defaulted to the ontology order"
        )
    if isinstance(class_order, (str, bytes)):
        raise ClassOrderError("class_order must be a sequence of class names")
    declared = list(class_order)
    if not declared:
        raise ClassOrderError("class_order must not be empty")
    if any(not isinstance(name, str) or not name for name in declared):
        raise ClassOrderError("class_order entries must be non-empty class names")
    expected = list(ontology_class_names)
    if len(declared) != len(expected):
        raise ClassOrderError(
            f"class_order must list exactly {len(expected)} classes, "
            f"got {len(declared)}"
        )
    if len(set(declared)) != len(declared):
        duplicates = sorted({name for name in declared if declared.count(name) > 1})
        raise ClassOrderError(f"class_order repeats class names: {duplicates}")
    if sorted(declared) != sorted(expected):
        unknown = sorted(set(declared) - set(expected))
        missing = sorted(set(expected) - set(declared))
        raise ClassOrderError(
            "class_order must be a permutation of the frozen ontology names; "
            f"unknown={unknown} missing={missing}"
        )
    return {name: expected.index(name) for name in declared}


def parse_accepted_images(text: str) -> tuple[AcceptedImage, ...]:
    """Parse the approved ``N. /Session S/FILENAME`` list."""

    accepted: list[AcceptedImage] = []
    for raw_line in text.splitlines():
        match = ACCEPTED_PATTERN.match(raw_line.strip())
        if match is None:
            continue
        accepted.append(
            AcceptedImage(
                number=int(match.group(1)),
                session=int(match.group(2)),
                filename=match.group(3).strip(),
            )
        )
    if not accepted:
        raise TargetTestSetError("accepted image list contains no approved entries")
    if [item.number for item in accepted] != list(range(1, len(accepted) + 1)):
        raise TargetTestSetError("accepted image list is not consecutively numbered")
    stems = [item.stem for item in accepted]
    if len(set(stems)) != len(stems):
        repeated = sorted({stem for stem in stems if stems.count(stem) > 1})
        raise TargetTestSetError(f"accepted image list repeats image stems: {repeated}")
    return tuple(accepted)


def _discover_label_files(labels_root: Path) -> dict[str, Path]:
    """Map image stem to label file, rejecting stray or duplicated members."""

    found: dict[str, Path] = {}
    for path in sorted(labels_root.rglob("*.txt")):
        if not path.is_file():
            continue
        if path.name.startswith("._"):
            continue
        if any(part in IGNORED_LABEL_NAMES for part in path.parts):
            continue
        if path.name.lower() == "classes.txt":
            # Keep this file: it is the only artifact that could corroborate an
            # order otherwise taken on trust. Stop so a human reconciles it.
            listed = ", ".join(path.read_text(encoding="utf-8-sig").split()) or "<empty>"
            raise TargetTestSetError(
                f"{path.name} is present in the label export and is not treated as "
                "authoritative, because the order a MakeSense export was labeled in "
                "cannot be proven from the export. It lists: "
                f"[{listed}]. Compare that against the class_order argument, confirm "
                "the order with the labeler, then move this file outside the label "
                "directory (keep it as provenance) and re-run."
            )
        if path.stem in found:
            raise TargetTestSetError(
                f"label stem {path.stem!r} appears more than once: "
                f"{found[path.stem].name} and {path.name}"
            )
        found[path.stem] = path
    # An empty result is deliberately not a raise. A missing batch and a missing
    # whole export are the same kind of problem, so both are reported the same
    # way: one explicit ``missing_label_file`` exclusion per accepted image,
    # which names exactly what did not come back and blocks the freeze.
    return found


def _parse_label_lines(
    content: str,
    *,
    class_count: int,
) -> tuple[tuple[int, NormalizedBox], ...]:
    """Parse ``class_id cx cy w h`` lines, reporting every bad line at once.

    The final line of a MakeSense export has no trailing newline;
    ``str.splitlines`` handles that without special casing.
    """

    parsed: list[tuple[int, NormalizedBox]] = []
    problems: list[str] = []
    lines = [line.strip() for line in content.splitlines()]
    if not any(lines):
        raise ValueError("label file is empty")
    for line_number, line in enumerate(lines, start=1):
        if not line:
            continue
        fields = line.split()
        if len(fields) != 5:
            problems.append(
                f"line {line_number}: expected 5 fields, found {len(fields)}"
            )
            continue
        try:
            exported_class_id = int(fields[0])
            x_center, y_center, width, height = (float(value) for value in fields[1:])
        except ValueError as error:
            problems.append(f"line {line_number}: non-numeric field ({error})")
            continue
        if exported_class_id not in range(class_count):
            problems.append(
                f"line {line_number}: exported class ID {exported_class_id} is outside "
                f"0-{class_count - 1} of the recorded class order"
            )
            continue
        box = NormalizedBox(
            xmin=x_center - width / 2,
            ymin=y_center - height / 2,
            xmax=x_center + width / 2,
            ymax=y_center + height / 2,
        )
        box_errors = box.validation_errors()
        if box_errors:
            problems.append(
                f"line {line_number}: invalid box "
                f"({x_center}, {y_center}, {width}, {height}): "
                + "; ".join(box_errors)
            )
            continue
        parsed.append((exported_class_id, box))
    if problems:
        raise ValueError(" | ".join(problems))
    return tuple(parsed)


def ingest_target_test_set(
    paths: ProjectPaths,
    *,
    class_order: Sequence[str],
    accepted_list_path: str | Path,
    labels_root: str | Path,
    image_roots: Mapping[int, str | Path],
    expected_image_count: int,
    ontology_path: str | Path | None = None,
    source_id: str = TARGET_TEST_SOURCE_ID,
    source_version: str = "v1",
) -> TargetTestIngestReport:
    """Read the returned labels and report what a freeze would contain.

    ``class_order`` is keyword-only and has no default: omitting it raises
    ``TypeError`` before any file is read. ``expected_image_count`` and
    ``accepted_list_path`` are likewise explicit; no image count is hardcoded.

    Nothing is written. Use :func:`write_frozen_test_manifest` to freeze a
    report whose :attr:`TargetTestIngestReport.ok` is true.
    """

    ontology_source = (
        paths.project_root / "ontology.yaml" if ontology_path is None else ontology_path
    )
    ontology_document = load_yaml_mapping(ontology_source)
    ontology_version = str(ontology_document.get("ontology_version", ""))
    ontology_class_names = load_ontology_class_names(ontology_source)
    name_to_canonical_id = resolve_class_order(class_order, ontology_class_names)
    recorded_class_order = tuple(class_order)

    if not isinstance(expected_image_count, int) or expected_image_count <= 0:
        raise TargetTestSetError("expected_image_count must be a positive integer")

    data_root = paths.data_root
    accepted_list = require_path_within(accepted_list_path, data_root)
    labels_directory = require_path_within(labels_root, data_root)
    resolved_image_roots = {
        int(session): require_path_within(root, data_root)
        for session, root in image_roots.items()
    }
    if not resolved_image_roots:
        raise TargetTestSetError("image_roots must name at least one capture session")

    accepted = parse_accepted_images(accepted_list.read_text(encoding="utf-8-sig"))
    if len(accepted) != expected_image_count:
        raise TargetTestSetError(
            f"accepted image list holds {len(accepted)} images, "
            f"expected {expected_image_count}"
        )

    label_files = _discover_label_files(labels_directory)
    accepted_by_stem = {item.stem: item for item in accepted}

    images: list[CanonicalImage] = []
    exclusions: list[ExclusionEvent] = []
    accepted_without_labels: list[str] = []

    for item in accepted:
        image_id = f"{source_id}:session-{item.session}:{item.stem}"
        label_path = label_files.get(item.stem)
        if label_path is None:
            accepted_without_labels.append(item.stem)
            exclusions.append(
                ExclusionEvent(
                    source_id=source_id,
                    image_id=image_id,
                    annotation_id=None,
                    source_class=None,
                    action="missing_label_file",
                    reason=(
                        "accepted image has no returned label file; resolve with the "
                        "labeler before freezing"
                    ),
                )
            )
            continue

        session_root = resolved_image_roots.get(item.session)
        if session_root is None:
            exclusions.append(
                ExclusionEvent(
                    source_id=source_id,
                    image_id=image_id,
                    annotation_id=None,
                    source_class=None,
                    action="missing_session_root",
                    reason=f"no image root supplied for session {item.session}",
                )
            )
            continue
        image_path = session_root / item.filename
        if not image_path.is_file():
            exclusions.append(
                ExclusionEvent(
                    source_id=source_id,
                    image_id=image_id,
                    annotation_id=None,
                    source_class=None,
                    action="missing_image_file",
                    reason=f"accepted image file is absent: {item.filename}",
                )
            )
            continue

        try:
            parsed_boxes = _parse_label_lines(
                label_path.read_text(encoding="utf-8-sig"),
                class_count=len(recorded_class_order),
            )
        except ValueError as error:
            exclusions.append(
                ExclusionEvent(
                    source_id=source_id,
                    image_id=image_id,
                    annotation_id=None,
                    source_class=None,
                    action="invalid_label_file",
                    reason=f"{label_path.name}: {error}",
                )
            )
            continue

        try:
            width, height = visually_oriented_size(image_path)
        except (OSError, ValueError) as error:
            exclusions.append(
                ExclusionEvent(
                    source_id=source_id,
                    image_id=image_id,
                    annotation_id=None,
                    source_class=None,
                    action="unreadable_image_file",
                    reason=f"{item.filename}: {type(error).__name__}: {error}",
                )
            )
            continue

        annotations = tuple(
            CanonicalAnnotation(
                annotation_id=f"{image_id}#{index}",
                source_class=f"makesense_class_{exported_class_id}",
                class_id=name_to_canonical_id[recorded_class_order[exported_class_id]],
                class_name=recorded_class_order[exported_class_id],
                box=box,
            )
            for index, (exported_class_id, box) in enumerate(parsed_boxes, start=1)
        )
        images.append(
            CanonicalImage(
                image_id=image_id,
                source_id=source_id,
                source_version=source_version,
                relative_path=image_path.relative_to(data_root).as_posix(),
                width=width,
                height=height,
                group_id=f"session-{item.session}",
                annotations=annotations,
                exact_hash=sha256_file(image_path),
            )
        )

    labels_without_accepted_image = tuple(
        sorted(stem for stem in label_files if stem not in accepted_by_stem)
    )
    for stem in labels_without_accepted_image:
        exclusions.append(
            ExclusionEvent(
                source_id=source_id,
                image_id=f"{source_id}:unmatched:{stem}",
                annotation_id=None,
                source_class=None,
                action="unmatched_label_file",
                reason=(
                    f"{label_files[stem].name} has no entry in the accepted image "
                    "list; it was never approved for annotation"
                ),
            )
        )

    audit = audit_canonical_images(
        images,
        source_roots={source_id: data_root},
        verify_image_files=True,
    )

    return TargetTestIngestReport(
        source_id=source_id,
        source_version=source_version,
        ontology_version=ontology_version,
        ontology_class_names=ontology_class_names,
        recorded_class_order=recorded_class_order,
        class_order_to_canonical_id=dict(sorted(name_to_canonical_id.items())),
        images=tuple(sorted(images, key=lambda image: image.image_id)),
        exclusions=tuple(exclusions),
        audit=audit,
        accepted_without_labels=tuple(accepted_without_labels),
        labels_without_accepted_image=labels_without_accepted_image,
        accepted_list_relative_path=accepted_list.relative_to(data_root).as_posix(),
        accepted_list_sha256=sha256_file(accepted_list),
        expected_image_count=expected_image_count,
        accepted_image_count=len(accepted),
    )


def _manifest_body(
    report: TargetTestIngestReport,
    *,
    manifest_id: str,
    frozen_on: str,
) -> dict[str, Any]:
    images: list[dict[str, Any]] = []
    class_counts: Counter[str] = Counter()
    session_counts: Counter[str] = Counter()
    for image in report.images:
        session_counts[image.group_id] += 1
        boxes: list[dict[str, Any]] = []
        for annotation in image.annotations:
            x_center, y_center, width, height = annotation.box.as_yolo()
            class_counts[annotation.class_name] += 1
            boxes.append(
                {
                    "annotation_id": annotation.annotation_id,
                    "canonical_class_id": annotation.class_id,
                    "canonical_class_name": annotation.class_name,
                    "exported_class": annotation.source_class,
                    "x_center": x_center,
                    "y_center": y_center,
                    "width": width,
                    "height": height,
                }
            )
        images.append(
            {
                "image_id": image.image_id,
                "capture_session": image.group_id,
                "relative_path": image.relative_path,
                "sha256": image.exact_hash,
                "width": image.width,
                "height": image.height,
                "boxes": boxes,
            }
        )

    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "manifest_id": manifest_id,
        "frozen_on": frozen_on,
        "source_id": report.source_id,
        "source_version": report.source_version,
        "role": "target_test",
        "include_in_training": False,
        "include_in_evaluation": True,
        "ontology_version": report.ontology_version,
        "ontology_class_names": list(report.ontology_class_names),
        "recorded_class_order": list(report.recorded_class_order),
        "class_order_to_canonical_id": dict(report.class_order_to_canonical_id),
        "accepted_list": {
            "relative_path": report.accepted_list_relative_path,
            "sha256": report.accepted_list_sha256,
            "expected_image_count": report.expected_image_count,
            "accepted_image_count": report.accepted_image_count,
        },
        "counts": {
            "images": len(report.images),
            "boxes": report.box_count,
            "images_by_capture_session": dict(sorted(session_counts.items())),
            "boxes_by_canonical_class": dict(sorted(class_counts.items())),
        },
        "images": images,
        "exclusions": [asdict(item) for item in report.exclusions],
        "audit": {
            "ok": report.audit.ok,
            "image_counts_by_source": report.audit.image_counts_by_source,
            "annotation_counts_by_class": report.audit.annotation_counts_by_class,
            "findings": [asdict(item) for item in report.audit.findings],
        },
    }


def write_frozen_test_manifest(
    report: TargetTestIngestReport,
    destination: str | Path,
    *,
    paths: ProjectPaths,
    manifest_id: str,
    frozen_on: str | None = None,
) -> Path:
    """Write one new frozen manifest; refuse to overwrite an existing one.

    Like :func:`src.release.write_yolo_release`, an existing destination is a
    hard error: a frozen target test set is never rewritten in place, because
    Phase 9 and Phase 10 require it to stay identical across experiments.
    """

    if not report.ok:
        raise TargetTestSetError(
            "cannot freeze a target test set with exclusions or audit errors:\n"
            + report.render()
        )
    output_directory = require_path_within(
        destination, paths.output_root, must_exist=False
    )
    manifest_path = output_directory / MANIFEST_FILENAME
    if manifest_path.exists():
        raise FileExistsError(
            f"refusing to overwrite frozen target test manifest: {manifest_path}"
        )
    body = _manifest_body(
        report,
        manifest_id=manifest_id,
        frozen_on=frozen_on or date.today().isoformat(),
    )
    document = dict(body)
    document["manifest_checksum"] = _checksum_of(body)
    output_directory.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(document, indent=2, sort_keys=True) + "\n")
    return manifest_path


def verify_frozen_test_manifest(
    manifest_path: str | Path,
    *,
    data_root: str | Path | None = None,
) -> tuple[str, ...]:
    """Recompute the manifest checksum and, optionally, the image evidence.

    Returns the problems found. A non-empty result means the frozen test set is
    no longer trustworthy: either the manifest was edited after freezing or the
    images it pins have changed on disk. When ``data_root`` is supplied, each
    image's SHA-256 and visually oriented dimensions are re-derived from the
    file and compared with the frozen values.
    """

    source = Path(manifest_path)
    document = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise TargetTestSetError(f"{source} must contain a JSON object")

    problems: list[str] = []
    recorded_checksum = document.get("manifest_checksum")
    body = {key: value for key, value in document.items() if key != "manifest_checksum"}
    actual_checksum = _checksum_of(body)
    if recorded_checksum != actual_checksum:
        problems.append(
            f"manifest checksum mismatch: recorded={recorded_checksum} "
            f"actual={actual_checksum}"
        )

    if data_root is not None:
        root = Path(data_root)
        for image in document.get("images", []):
            image_id = image.get("image_id", "<unknown>")
            image_path = root / str(image.get("relative_path", ""))
            if not image_path.is_file():
                problems.append(f"{image_id}: frozen image file is absent")
                continue
            if sha256_file(image_path) != image.get("sha256"):
                problems.append(f"{image_id}: image bytes changed since the freeze")
            try:
                actual_size = visually_oriented_size(image_path)
            except (OSError, ValueError) as error:
                problems.append(f"{image_id}: image is unreadable ({type(error).__name__})")
                continue
            frozen_size = (image.get("width"), image.get("height"))
            if actual_size != frozen_size:
                problems.append(
                    f"{image_id}: dimension mismatch frozen={frozen_size} "
                    f"actual={actual_size}"
                )
    return tuple(problems)


def read_frozen_class_order(manifest_path: str | Path) -> tuple[str, ...]:
    """Return the labeling class order recorded verbatim in a frozen manifest."""

    document = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    order: Iterable[Any] = document.get("recorded_class_order", ())
    return tuple(str(name) for name in order)
