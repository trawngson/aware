"""Ontology-driven minimum box-size policy at the 640-pixel training view."""

from __future__ import annotations

from .canonical_data import NormalizedBox


TRAINING_IMAGE_SIZE = 640
GENERAL_MINIMUM_SHORT_SIDE = 12.0
STYROFOAM_MINIMUM_SHORT_SIDE = 20.0


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
