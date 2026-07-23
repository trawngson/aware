"""Image-file helpers that preserve raw data while honoring EXIF orientation."""

from __future__ import annotations

from pathlib import Path


EXIF_ORIENTATION_TAG = 274
TRANSPOSE_ORIENTATIONS = frozenset(range(2, 9))


def visually_oriented_size(path: str | Path) -> tuple[int, int]:
    """Decode an image and return its size after applying EXIF orientation."""

    from PIL import Image, ImageOps

    with Image.open(path) as image:
        oriented = ImageOps.exif_transpose(image)
        oriented.load()
        return oriented.size


def materialize_exif_oriented_copy(
    source: str | Path,
    destination: str | Path,
    *,
    expected_size: tuple[int, int],
) -> int | None:
    """Write a visually oriented derived copy when EXIF requires transposition.

    Raw files are never modified. JPEG encoding settings and non-orientation
    EXIF metadata are retained where Pillow supports them. The applied source
    orientation is returned for release-manifest provenance.
    """

    from PIL import Image, ImageOps

    source_path = Path(source)
    destination_path = Path(destination)
    with Image.open(source_path) as image:
        orientation = int(image.getexif().get(EXIF_ORIENTATION_TAG, 1))
        oriented = ImageOps.exif_transpose(image)
        oriented.load()
        if oriented.size != expected_size:
            raise ValueError(
                f"visually oriented size mismatch for {source_path}: "
                f"expected={expected_size} actual={oriented.size}"
            )
        if orientation not in TRANSPOSE_ORIENTATIONS:
            return None

        image_format = image.format
        if not image_format:
            raise ValueError(f"image format is unavailable for {source_path}")
        oriented.format = image_format

        save_options: dict[str, object] = {}
        if image_format == "JPEG":
            save_options["quality"] = "keep"
            save_options["subsampling"] = "keep"
        if image.info.get("icc_profile") is not None:
            save_options["icc_profile"] = image.info["icc_profile"]
        if image.info.get("dpi") is not None:
            save_options["dpi"] = image.info["dpi"]
        normalized_exif = oriented.getexif()
        if normalized_exif:
            save_options["exif"] = normalized_exif

        oriented.save(destination_path, format=image_format, **save_options)

    with Image.open(destination_path) as written:
        written.load()
        written_orientation = int(written.getexif().get(EXIF_ORIENTATION_TAG, 1))
        if written.size != expected_size:
            raise ValueError(
                f"normalized output size mismatch for {destination_path}: "
                f"expected={expected_size} actual={written.size}"
            )
        if written_orientation != 1:
            raise ValueError(
                f"normalized output retained EXIF orientation {written_orientation}: "
                f"{destination_path}"
            )
    return orientation
