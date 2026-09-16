#!/usr/bin/env python3
"""Validate returned MakeSense YOLO labels and render a visual review gallery."""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import shutil
import subprocess
import tempfile
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


CLASS_NAMES = (
    "plastic_bottle",
    "glass_container",
    "metal_can",
    "cardboard",
    "plastic_bag",
    "disposable_cup",
    "styrofoam",
)
CLASS_COLORS = (
    (255, 45, 85),
    (0, 122, 255),
    (255, 149, 0),
    (175, 82, 222),
    (52, 199, 89),
    (255, 204, 0),
    (90, 200, 250),
)
ACCEPTED_PATTERN = re.compile(r"^(\d+)\.\s+/Session\s+([12])/(\S+)$")
BATCH_SIZE = 20
RENDER_MAXIMUM_SIDE = 2200
THUMBNAIL_SIZE = (360, 270)
CONTACT_COLUMNS = 4
CONTACT_ROWS = 5


@dataclass(frozen=True)
class AcceptedImage:
    number: int
    session: int
    filename: str

    @property
    def stem(self) -> str:
        return Path(self.filename).stem

    @property
    def batch(self) -> int:
        return ((self.number - 1) // BATCH_SIZE) + 1


@dataclass(frozen=True)
class Box:
    class_id: int
    x_center: float
    y_center: float
    width: float
    height: float

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        return (
            self.x_center - self.width / 2,
            self.y_center - self.height / 2,
            self.x_center + self.width / 2,
            self.y_center + self.height / 2,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--accepted-list", type=Path, required=True)
    parser.add_argument("--labels-directory", type=Path, required=True)
    parser.add_argument("--session-1", type=Path, required=True)
    parser.add_argument("--session-2", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def load_accepted(path: Path) -> list[AcceptedImage]:
    accepted: list[AcceptedImage] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        match = ACCEPTED_PATTERN.match(raw_line.strip())
        if match:
            accepted.append(
                AcceptedImage(
                    number=int(match.group(1)),
                    session=int(match.group(2)),
                    filename=match.group(3),
                )
            )
    if [item.number for item in accepted] != list(range(1, len(accepted) + 1)):
        raise ValueError("accepted image list is not consecutively numbered")
    return accepted


def parse_label_file(
    *, filename: str, content: str
) -> tuple[list[Box], list[str], list[str]]:
    boxes: list[Box] = []
    errors: list[str] = []
    warnings: list[str] = []
    nonempty_lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not nonempty_lines:
        errors.append(f"{filename}: label file is empty")
        return boxes, errors, warnings

    seen: set[tuple[int, float, float, float, float]] = set()
    for line_number, line in enumerate(nonempty_lines, start=1):
        fields = line.split()
        prefix = f"{filename}:{line_number}"
        if len(fields) != 5:
            errors.append(f"{prefix}: expected 5 fields, found {len(fields)}")
            continue
        try:
            class_id = int(fields[0])
            values = tuple(float(value) for value in fields[1:])
        except ValueError:
            errors.append(f"{prefix}: class or coordinate is not numeric")
            continue
        if class_id not in range(len(CLASS_NAMES)):
            errors.append(f"{prefix}: class ID {class_id} is outside 0-6")
            continue
        if not all(math.isfinite(value) for value in values):
            errors.append(f"{prefix}: coordinate is not finite")
            continue
        box = Box(class_id, *values)
        xmin, ymin, xmax, ymax = box.bounds
        if box.width <= 0 or box.height <= 0:
            errors.append(f"{prefix}: box width and height must be positive")
            continue
        if not all(0 <= value <= 1 for value in (xmin, ymin, xmax, ymax)):
            errors.append(
                f"{prefix}: box crosses the image boundary "
                f"({xmin:.6f}, {ymin:.6f}, {xmax:.6f}, {ymax:.6f})"
            )
            continue
        signature = (class_id, *values)
        if signature in seen:
            warnings.append(f"{prefix}: exact duplicate box")
        seen.add(signature)
        if box.width * box.height > 0.9:
            warnings.append(f"{prefix}: box covers more than 90% of the image")
        boxes.append(box)

    for first_index, first in enumerate(boxes, start=1):
        for second_index, second in enumerate(
            boxes[first_index:], start=first_index + 1
        ):
            if first.class_id != second.class_id:
                continue
            first_xmin, first_ymin, first_xmax, first_ymax = first.bounds
            second_xmin, second_ymin, second_xmax, second_ymax = second.bounds
            intersection_width = max(
                0.0, min(first_xmax, second_xmax) - max(first_xmin, second_xmin)
            )
            intersection_height = max(
                0.0, min(first_ymax, second_ymax) - max(first_ymin, second_ymin)
            )
            intersection = intersection_width * intersection_height
            smaller_area = min(
                first.width * first.height, second.width * second.height
            )
            containment = intersection / smaller_area if smaller_area > 0 else 0.0
            if containment >= 0.9:
                warnings.append(
                    f"{filename}: boxes {first_index} and {second_index} are nested "
                    f"same-class boxes ({containment:.1%} containment); inspect for an "
                    "incorrect separate cap, lid, or pump box"
                )
    return boxes, errors, warnings


def load_labels(
    accepted: list[AcceptedImage], labels_directory: Path
) -> tuple[dict[str, list[Box]], dict[str, object]]:
    expected_by_batch = {
        batch: {
            f"{item.stem}.txt" for item in accepted if item.batch == batch
        }
        for batch in range(1, 7)
    }
    boxes_by_stem: dict[str, list[Box]] = {}
    missing_by_batch: dict[str, list[str]] = {}
    unexpected_by_batch: dict[str, list[str]] = {}
    errors: list[str] = []
    warnings: list[str] = []
    archive_counts: dict[str, int] = {}

    for batch in range(1, 7):
        archive = labels_directory / f"batch_{batch:02d}_labels.zip"
        if not archive.is_file():
            errors.append(f"missing archive: {archive.name}")
            missing_by_batch[str(batch)] = sorted(expected_by_batch[batch])
            archive_counts[str(batch)] = 0
            continue
        with zipfile.ZipFile(archive) as handle:
            members = [
                member
                for member in handle.infolist()
                if not member.is_dir() and not member.filename.startswith("__MACOSX/")
            ]
            flat_txt_names = {
                Path(member.filename).name
                for member in members
                if Path(member.filename).suffix.lower() == ".txt"
            }
            archive_counts[str(batch)] = len(flat_txt_names)
            missing = sorted(expected_by_batch[batch] - flat_txt_names)
            unexpected = sorted(flat_txt_names - expected_by_batch[batch])
            if missing:
                missing_by_batch[str(batch)] = missing
            if unexpected:
                unexpected_by_batch[str(batch)] = unexpected
            for member in members:
                member_path = Path(member.filename)
                if member_path.suffix.lower() != ".txt":
                    warnings.append(
                        f"{archive.name}: ignored non-TXT member {member.filename}"
                    )
                    continue
                simple_name = member_path.name
                if simple_name not in expected_by_batch[batch]:
                    continue
                content = handle.read(member).decode("utf-8-sig")
                boxes, file_errors, file_warnings = parse_label_file(
                    filename=simple_name, content=content
                )
                boxes_by_stem[Path(simple_name).stem] = boxes
                errors.extend(file_errors)
                warnings.extend(file_warnings)

    return boxes_by_stem, {
        "archive_counts": archive_counts,
        "missing_by_batch": missing_by_batch,
        "unexpected_by_batch": unexpected_by_batch,
        "errors": errors,
        "warnings": warnings,
    }


def source_path(
    item: AcceptedImage, session_one: Path, session_two: Path
) -> Path:
    return (session_one if item.session == 1 else session_two) / item.filename


def convert_heic(source: Path, destination: Path) -> None:
    converter = shutil.which("heif-convert")
    if converter is None:
        raise RuntimeError("heif-convert is required to render the HEIC review images")
    result = subprocess.run(
        [converter, "-q", "92", str(source), str(destination)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not destination.is_file():
        raise RuntimeError(
            f"failed to convert {source.name}: {(result.stderr or result.stdout).strip()}"
        )


def fit_for_review(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("RGB")
    if max(image.size) > RENDER_MAXIMUM_SIDE:
        image.thumbnail(
            (RENDER_MAXIMUM_SIDE, RENDER_MAXIMUM_SIDE), Image.Resampling.LANCZOS
        )
    return image


def text_font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def render_annotated(
    *, converted: Path, destination: Path, item: AcceptedImage, boxes: list[Box] | None
) -> Image.Image:
    with Image.open(converted) as handle:
        image = fit_for_review(handle.copy())
    draw = ImageDraw.Draw(image)
    font = text_font(max(18, round(max(image.size) / 90)))
    line_width = max(4, round(max(image.size) / 350))

    if boxes is None:
        banner_height = max(60, image.height // 12)
        draw.rectangle((0, 0, image.width, banner_height), fill=(190, 0, 0))
        draw.text(
            (12, 10),
            "MISSING LABEL FILE — RETURN TO ANNOTATOR",
            fill="white",
            font=font,
        )
    else:
        for index, box in enumerate(boxes, start=1):
            xmin, ymin, xmax, ymax = box.bounds
            rectangle = (
                round(xmin * image.width),
                round(ymin * image.height),
                round(xmax * image.width),
                round(ymax * image.height),
            )
            color = CLASS_COLORS[box.class_id]
            draw.rectangle(rectangle, outline=color, width=line_width)
            label = f"{index}: {CLASS_NAMES[box.class_id]}"
            left, top, right, bottom = draw.textbbox((0, 0), label, font=font)
            text_width = right - left
            text_height = bottom - top
            label_x = max(0, min(rectangle[0], image.width - text_width - 12))
            label_y = max(0, rectangle[1] - text_height - 12)
            draw.rectangle(
                (label_x, label_y, label_x + text_width + 12, label_y + text_height + 10),
                fill=color,
            )
            draw.text((label_x + 6, label_y + 3), label, fill="black", font=font)

    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, quality=92, optimize=True)
    return image


def render_contact_sheet(
    *, batch: int, items: list[AcceptedImage], annotated_directory: Path, destination: Path
) -> None:
    header_height = 38
    tile_width, tile_height = THUMBNAIL_SIZE
    sheet = Image.new(
        "RGB",
        (
            CONTACT_COLUMNS * tile_width,
            CONTACT_ROWS * (tile_height + header_height),
        ),
        (225, 225, 225),
    )
    font = text_font(21)
    for position, item in enumerate(items):
        with Image.open(annotated_directory / f"{item.stem}.jpg") as handle:
            thumbnail = handle.convert("RGB")
            thumbnail.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
        tile = Image.new("RGB", (tile_width, tile_height + header_height), "white")
        x_offset = (tile_width - thumbnail.width) // 2
        y_offset = header_height + (tile_height - thumbnail.height) // 2
        tile.paste(thumbnail, (x_offset, y_offset))
        ImageDraw.Draw(tile).text(
            (8, 8), f"#{item.number}  {item.stem}", fill="black", font=font
        )
        x = (position % CONTACT_COLUMNS) * tile_width
        y = (position // CONTACT_COLUMNS) * (tile_height + header_height)
        sheet.paste(tile, (x, y))
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination, quality=93, optimize=True)


def build_gallery(
    *, accepted: list[AcceptedImage], boxes_by_stem: dict[str, list[Box]], output: Path
) -> None:
    legend = "".join(
        f'<span><i style="background:rgb{CLASS_COLORS[index]}"></i>{html.escape(name)}</span>'
        for index, name in enumerate(CLASS_NAMES)
    )
    sections: list[str] = []
    for batch in range(1, 7):
        cards: list[str] = []
        for item in accepted:
            if item.batch != batch:
                continue
            boxes = boxes_by_stem.get(item.stem)
            status = "MISSING" if boxes is None else f"{len(boxes)} box(es)"
            status_class = "missing" if boxes is None else "present"
            class_summary = ""
            if boxes:
                counts = Counter(CLASS_NAMES[box.class_id] for box in boxes)
                class_summary = ", ".join(
                    f"{name} ×{count}" for name, count in sorted(counts.items())
                )
            cards.append(
                f'''<article class="card {status_class}">
                <a href="annotated/{item.stem}.jpg" target="_blank">
                  <img src="annotated/{item.stem}.jpg" loading="lazy" alt="{item.stem}">
                </a>
                <div><strong>#{item.number} {item.stem}</strong><b>{status}</b></div>
                <p>{html.escape(class_summary)}</p>
                </article>'''
            )
        sections.append(
            f'<section><h2>Batch {batch:02d}</h2><div class="grid">{"".join(cards)}</div></section>'
        )
    document = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AWARE returned-label review</title>
<style>
body{{font:16px system-ui,sans-serif;margin:24px;background:#f3f4f6;color:#111827}}
h1{{margin-bottom:4px}} h2{{margin-top:40px}}
.note{{color:#4b5563}} .legend{{display:flex;flex-wrap:wrap;gap:14px;margin:18px 0}}
.legend span{{display:flex;align-items:center;gap:6px}} .legend i{{width:18px;height:18px;border-radius:4px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:18px}}
.card{{background:white;border:3px solid #d1d5db;border-radius:10px;overflow:hidden;box-shadow:0 1px 4px #0002}}
.card.missing{{border-color:#be0000}} .card img{{display:block;width:100%;aspect-ratio:4/3;object-fit:contain;background:#111}}
.card div{{display:flex;justify-content:space-between;gap:8px;padding:10px 12px 0}}
.card b{{color:#166534}} .card.missing b{{color:#be0000}} .card p{{min-height:1.2em;margin:6px 12px 12px;color:#4b5563}}
</style></head><body>
<h1>AWARE returned-label visual review</h1>
<p class="note">Click any image to inspect the box at a larger size. Red banners identify missing label files.</p>
<div class="legend">{legend}</div>
{"".join(sections)}
</body></html>'''
    (output / "gallery.html").write_text(document, encoding="utf-8")


def write_reports(
    *, accepted: list[AcceptedImage], boxes_by_stem: dict[str, list[Box]], validation: dict[str, object], output: Path
) -> None:
    class_counts = Counter(
        CLASS_NAMES[box.class_id]
        for boxes in boxes_by_stem.values()
        for box in boxes
    )
    missing_by_batch = validation["missing_by_batch"]
    invalid_errors = validation["errors"]
    unexpected_by_batch = validation["unexpected_by_batch"]
    total_boxes = sum(len(boxes) for boxes in boxes_by_stem.values())
    automatic_pass = not missing_by_batch and not invalid_errors and not unexpected_by_batch
    report = {
        "automatic_validation_pass": automatic_pass,
        "expected_images": len(accepted),
        "returned_label_files": len(boxes_by_stem),
        "total_boxes": total_boxes,
        "class_counts": dict(sorted(class_counts.items())),
        **validation,
    }
    (output / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )

    lines = [
        "# AWARE returned-label QA report",
        "",
        f"Automatic validation: **{'PASS' if automatic_pass else 'FAIL'}**",
        "",
        f"- Expected images: {len(accepted)}",
        f"- Returned label files: {len(boxes_by_stem)}",
        f"- Missing label files: {len(accepted) - len(boxes_by_stem)}",
        f"- Parsed boxes: {total_boxes}",
        f"- Invalid label/coordinate errors: {len(invalid_errors)}",
        "",
        "## Missing files",
        "",
    ]
    if missing_by_batch:
        for batch, names in sorted(missing_by_batch.items(), key=lambda item: int(item[0])):
            lines.append(f"- Batch {int(batch):02d}: {', '.join(names)}")
    else:
        lines.append("- None")
    lines.extend(["", "## Class counts", ""])
    for class_name in CLASS_NAMES:
        lines.append(f"- `{class_name}`: {class_counts[class_name]}")
    lines.extend(["", "## Invalid labels or coordinates", ""])
    if invalid_errors:
        lines.extend(f"- {error}" for error in invalid_errors)
    else:
        lines.append("- None")
    lines.extend(["", "## Warnings", ""])
    warnings = validation["warnings"]
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Required visual review",
            "",
            "Automatic checks cannot determine whether a box is tight or whether an eligible object was missed.",
            "Open `gallery.html`, inspect every image, and click an image whenever closer inspection is needed.",
        ]
    )
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"output already exists: {args.output}")
    accepted = load_accepted(args.accepted_list)
    if len(accepted) != 119:
        raise ValueError(f"expected 119 accepted images, found {len(accepted)}")
    boxes_by_stem, validation = load_labels(accepted, args.labels_directory)
    args.output.mkdir(parents=True)
    annotated_directory = args.output / "annotated"
    contacts_directory = args.output / "contact_sheets"

    with tempfile.TemporaryDirectory(prefix="aware-label-review-") as temporary:
        converted_directory = Path(temporary)
        for position, item in enumerate(accepted, start=1):
            source = source_path(item, args.session_1, args.session_2)
            if not source.is_file():
                raise FileNotFoundError(f"missing source image: {source}")
            converted = converted_directory / f"{item.stem}.jpg"
            convert_heic(source, converted)
            render_annotated(
                converted=converted,
                destination=annotated_directory / f"{item.stem}.jpg",
                item=item,
                boxes=boxes_by_stem.get(item.stem),
            )
            if position % 20 == 0 or position == len(accepted):
                print(f"Rendered review images: {position}/{len(accepted)}", flush=True)

    for batch in range(1, 7):
        batch_items = [item for item in accepted if item.batch == batch]
        render_contact_sheet(
            batch=batch,
            items=batch_items,
            annotated_directory=annotated_directory,
            destination=contacts_directory / f"batch_{batch:02d}.jpg",
        )
    build_gallery(accepted=accepted, boxes_by_stem=boxes_by_stem, output=args.output)
    write_reports(
        accepted=accepted,
        boxes_by_stem=boxes_by_stem,
        validation=validation,
        output=args.output,
    )
    print(f"QA output: {args.output}")


if __name__ == "__main__":
    main()
