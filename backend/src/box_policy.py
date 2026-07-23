"""Ontology-driven minimum box-size policy at the 640-pixel training view."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .canonical_data import NormalizedBox


TRAINING_IMAGE_SIZE = 640
GENERAL_MINIMUM_SHORT_SIDE = 12.0
STYROFOAM_MINIMUM_SHORT_SIDE = 20.0
MAX_SAFE_BOUNDARY_OVERFLOW_PIXELS = 2.0
MINIMUM_SAFE_RETAINED_AREA = 0.99


@dataclass(frozen=True)
class BoxBoundaryResult:
    box: NormalizedBox
    adjustment: dict[str, Any] | None
    review_reason: str | None


def normalize_coco_pixel_box(
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    image_width: int,
    image_height: int,
) -> BoxBoundaryResult:
    """Normalize COCO pixels, safely clipping only negligible boundary drift."""

    raw_values = (x, y, width, height)
    if (
        image_width <= 0
        or image_height <= 0
        or not all(math.isfinite(value) for value in raw_values)
        or width <= 0
        or height <= 0
    ):
        return BoxBoundaryResult(
            box=NormalizedBox(
                xmin=x / image_width if image_width else float("nan"),
                ymin=y / image_height if image_height else float("nan"),
                xmax=(x + width) / image_width if image_width else float("nan"),
                ymax=(y + height) / image_height if image_height else float("nan"),
            ),
            adjustment=None,
            review_reason="COCO box has non-finite values, non-positive size, or invalid image dimensions",
        )

    source_xmax = x + width
    source_ymax = y + height
    clipped_xmin = max(0.0, x)
    clipped_ymin = max(0.0, y)
    clipped_xmax = min(float(image_width), source_xmax)
    clipped_ymax = min(float(image_height), source_ymax)
    clipped_width = max(0.0, clipped_xmax - clipped_xmin)
    clipped_height = max(0.0, clipped_ymax - clipped_ymin)
    retained_area = (clipped_width * clipped_height) / (width * height)
    overflow = max(
        max(0.0, -x),
        max(0.0, -y),
        max(0.0, source_xmax - image_width),
        max(0.0, source_ymax - image_height),
    )
    crosses_boundary = overflow > 0
    if crosses_boundary and (
        overflow > MAX_SAFE_BOUNDARY_OVERFLOW_PIXELS
        or retained_area < MINIMUM_SAFE_RETAINED_AREA
        or clipped_width <= 0
        or clipped_height <= 0
    ):
        return BoxBoundaryResult(
            box=NormalizedBox(
                xmin=x / image_width,
                ymin=y / image_height,
                xmax=source_xmax / image_width,
                ymax=source_ymax / image_height,
            ),
            adjustment=None,
            review_reason=(
                f"box crosses image boundary by {overflow:.4f}px and retains "
                f"{retained_area:.6f} area; exceeds safe clipping policy"
            ),
        )

    box = NormalizedBox(
        xmin=clipped_xmin / image_width,
        ymin=clipped_ymin / image_height,
        xmax=clipped_xmax / image_width,
        ymax=clipped_ymax / image_height,
    )
    if not crosses_boundary:
        return BoxBoundaryResult(box=box, adjustment=None, review_reason=None)

    return BoxBoundaryResult(
        box=box,
        adjustment={
            "action": "clip_to_image_bounds",
            "source_format": "coco_xywh_pixels",
            "source_box": [x, y, width, height],
            "maximum_overflow_pixels": round(overflow, 6),
            "retained_area_fraction": round(retained_area, 9),
        },
        review_reason=None,
    )


def short_side_after_letterbox_resize(
    box: NormalizedBox,
    *,
    image_width: int,
    image_height: int,
    training_image_size: int = TRAINING_IMAGE_SIZE,
) -> float:
    """Return box short side after aspect-preserving resize before padding."""

    if image_width <= 0 or image_height <= 0:
        raise ValueError("image dimensions must be positive")
    if training_image_size <= 0:
        raise ValueError("training image size must be positive")
    scale = min(training_image_size / image_width, training_image_size / image_height)
    resized_width = box.width * image_width * scale
    resized_height = box.height * image_height * scale
    return min(resized_width, resized_height)


def minimum_short_side_for_class(class_name: str) -> float:
    return (
        STYROFOAM_MINIMUM_SHORT_SIDE
        if class_name == "styrofoam"
        else GENERAL_MINIMUM_SHORT_SIDE
    )


def minimum_size_review_reason(
    box: NormalizedBox,
    *,
    class_name: str,
    image_width: int,
    image_height: int,
) -> str | None:
    """Return a deterministic hold reason, or None when box passes."""

    if box.validation_errors():
        return None
    actual = short_side_after_letterbox_resize(
        box,
        image_width=image_width,
        image_height=image_height,
    )
    required = minimum_short_side_for_class(class_name)
    if actual >= required:
        return None
    return (
        f"box short side {actual:.2f}px at {TRAINING_IMAGE_SIZE}px training view "
        f"is below {required:.0f}px minimum for {class_name}"
    )
