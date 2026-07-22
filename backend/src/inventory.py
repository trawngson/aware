"""Read-only source inventory for a manually selected VAST kernel."""

from __future__ import annotations

import csv
import json
import shutil
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class SourceInventory:
    source_id: str
    path_status: str
    file_count: int
    total_bytes: int
    extensions: dict[str, int]
    image_count: int | None
    annotation_count: int | None
    class_names: tuple[str, ...]
    notes: tuple[str, ...]

    def render(self) -> str:
        size_gib = self.total_bytes / 1024**3
        lines = [f"source={self.source_id} status={self.path_status}"]
        lines.append(f"  files={self.file_count} bytes={self.total_bytes} GiB={size_gib:.2f}")
        lines.append(f"  extensions={self.extensions}")
        lines.append(f"  images={self.image_count} annotations={self.annotation_count}")
        lines.append(f"  classes={list(self.class_names)}")
        lines.extend(f"  note={note}" for note in self.notes)
        return "\n".join(lines)


def _contained_path(data_root: Path, relative_path: str) -> Path:
    if not relative_path:
        raise ValueError("source path must not be empty")
    root = data_root.resolve()
    candidate = (root / relative_path).resolve()
    if candidate == root or not candidate.is_relative_to(root):
        raise ValueError(f"source path leaves PROJECT_DATA_ROOT: {relative_path!r}")
    return candidate


def _read_coco_summary(path: Path) -> tuple[int | None, int | None, tuple[str, ...]]:
    with path.open("r", encoding="utf-8") as handle:
        document = json.load(handle)
    categories = document.get("categories", [])
    images = document.get("images", [])
    annotations = document.get("annotations", [])
    class_names = tuple(str(item["name"]) for item in categories if "name" in item)
    return len(images), len(annotations), class_names


def _read_class_csv(path: Path) -> tuple[str, ...]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return tuple(row[1] for row in csv.reader(handle) if len(row) >= 2)


def inventory_source(source_id: str, source_path: Path) -> SourceInventory:
    """Walk metadata read-only and summarize likely annotation formats."""

    if not source_path.exists():
        return SourceInventory(source_id, "missing", 0, 0, {}, None, None, (), ())
    if not source_path.is_dir():
        return SourceInventory(
            source_id,
            "not_a_directory",
            0,
            0,
            {},
            None,
            None,
            (),
            (),
        )

    extensions: Counter[str] = Counter()
    total_bytes = 0
    files: list[Path] = []
    notes: list[str] = []
    for path in source_path.rglob("*"):
        if path.is_file():
            files.append(path)
            extensions[path.suffix.lower() or "<none>"] += 1
            total_bytes += path.stat().st_size

    image_count: int | None = sum(
        extensions.get(extension, 0)
        for extension in (".jpg", ".jpeg", ".png", ".heic", ".webp")
    )
    annotation_count: int | None = None
    class_names: tuple[str, ...] = ()

    coco_candidates = [path for path in files if path.name in {"annotations.json", "instances.json"}]
    if len(coco_candidates) == 1:
        try:
            image_count, annotation_count, class_names = _read_coco_summary(coco_candidates[0])
            notes.append(f"COCO metadata: {coco_candidates[0].relative_to(source_path)}")
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
            notes.append(f"COCO metadata unreadable: {type(error).__name__}")

    class_csv_candidates = [path for path in files if "class-descriptions" in path.name]
    if not class_names and len(class_csv_candidates) == 1:
        try:
            class_names = _read_class_csv(class_csv_candidates[0])
            notes.append(f"class CSV: {class_csv_candidates[0].relative_to(source_path)}")
        except (OSError, ValueError, IndexError) as error:
            notes.append(f"class CSV unreadable: {type(error).__name__}")

    return SourceInventory(
        source_id=source_id,
        path_status="present",
        file_count=len(files),
        total_bytes=total_bytes,
        extensions=dict(sorted(extensions.items())),
        image_count=image_count,
        annotation_count=annotation_count,
        class_names=class_names,
        notes=tuple(notes),
    )


def inventory_approved_sources(
    data_root: str | Path,
    manifest: Mapping[str, Any],
) -> tuple[SourceInventory, ...]:
    root = Path(data_root)
    approved_ids = set(manifest["policy"]["approved_training_source_ids"])
    inventories: list[SourceInventory] = []
    for source in manifest["sources"]:
        if source["id"] not in approved_ids:
            continue
        relative_path = source["acquisition"]["raw_subdirectory"]
        path = _contained_path(root, relative_path)
        inventories.append(inventory_source(source["id"], path))
    return tuple(inventories)


def disk_summary(path: str | Path) -> str:
    usage = shutil.disk_usage(Path(path))
    return (
        f"disk total={usage.total} used={usage.used} free={usage.free} "
        f"free_GiB={usage.free / 1024**3:.2f}"
    )
