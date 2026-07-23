"""Canonical, source-traceable detection records used between pipeline stages."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


@dataclass(frozen=True)
class NormalizedBox:
    xmin: float
    ymin: float
    xmax: float
    ymax: float

    @property
    def width(self) -> float:
        return self.xmax - self.xmin

    @property
    def height(self) -> float:
        return self.ymax - self.ymin

    def validation_errors(self) -> tuple[str, ...]:
        values = (self.xmin, self.ymin, self.xmax, self.ymax)
        errors: list[str] = []
        if not all(math.isfinite(value) for value in values):
            errors.append("coordinates must be finite")
        if self.width <= 0 or self.height <= 0:
            errors.append("box must have positive width and height")
        if any(value < 0 or value > 1 for value in values):
            errors.append("coordinates must be within [0, 1]")
        return tuple(errors)

    def as_yolo(self) -> tuple[float, float, float, float]:
        return (
            (self.xmin + self.xmax) / 2,
            (self.ymin + self.ymax) / 2,
            self.width,
            self.height,
        )


@dataclass(frozen=True)
class CanonicalAnnotation:
    annotation_id: str
    source_class: str
    class_id: int
    class_name: str
    box: NormalizedBox
    box_adjustment: dict[str, Any] | None = None


@dataclass(frozen=True)
class CanonicalImage:
    image_id: str
    source_id: str
    source_version: str
    relative_path: str
    width: int
    height: int
    group_id: str
    annotations: tuple[CanonicalAnnotation, ...]
    exact_hash: str | None = None
    perceptual_hash: str | None = None
    attribution: dict[str, str] | None = None


@dataclass(frozen=True)
class ExclusionEvent:
    source_id: str
    image_id: str
    annotation_id: str | None
    source_class: str | None
    action: str
    reason: str


def safe_relative_path(value: str) -> str:
    """Return a normalized relative POSIX path or reject traversal/absolute paths."""

    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ValueError(f"unsafe relative path: {value!r}")
    return path.as_posix()


def image_to_dict(image: CanonicalImage) -> dict[str, Any]:
    return asdict(image)


def write_jsonl(records: Iterable[CanonicalImage], destination: str | Path) -> None:
    """Write a new canonical manifest; refuse to overwrite an existing release."""

    output = Path(destination)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite canonical manifest: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(image_to_dict(record), sort_keys=True) + "\n")
