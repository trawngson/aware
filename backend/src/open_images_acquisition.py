"""Resumable, integrity-checked acquisition of approved Open Images pixels."""

from __future__ import annotations

import base64
import binascii
import csv
import hashlib
import http.client
import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .dedup import sha256_file
from .image_files import EXIF_ORIENTATION_TAG, visually_oriented_size
from .open_images_preflight import sha256_file as metadata_sha256_file


DEFAULT_MIRROR_BASE_URL = "https://open-images-dataset.s3.amazonaws.com"
IMAGE_ID_PATTERN = re.compile(r"^[0-9a-f]{16}$")
SIMPLE_ETAG_PATTERN = re.compile(r"^[0-9a-f]{32}$")
COPY_CHUNK_SIZE = 1024 * 1024


class AcquisitionError(RuntimeError):
    """Raised when an acquisition cannot produce a complete verified release."""


@dataclass(frozen=True)
class RemoteObject:
    byte_count: int
    md5_hex: str


@dataclass(frozen=True)
class AcquiredImage:
    image_id: str
    relative_path: str
    status: str
    byte_count: int
    mirror_etag: str
    file_md5: str
    sha256: str
    raw_width: int
    raw_height: int
    visual_width: int
    visual_height: int
    exif_orientation: int


def _md5_file(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        while chunk := handle.read(COPY_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _decode_original_md5(value: str) -> str | None:
    """Decode Open Images' original-file MD5 for provenance reporting only."""

    encoded = value.strip()
    if not encoded:
        return None
    try:
        digest = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError, TypeError):
        return None
    return digest.hex() if len(digest) == 16 else None


def _simple_etag(value: str | None) -> str:
    if value is None:
        raise AcquisitionError("official mirror response is missing an ETag")
    normalized = value.strip().strip('"').lower()
    if not SIMPLE_ETAG_PATTERN.fullmatch(normalized):
        raise AcquisitionError(
            "official mirror ETag is not a single-part MD5: "
            f"{value!r}"
        )
    return normalized


def _remote_object_from_headers(headers: Any) -> RemoteObject:
    raw_size = headers.get("Content-Length")
    try:
        byte_count = int(raw_size)
    except (TypeError, ValueError) as error:
        raise AcquisitionError(
            f"official mirror response has invalid Content-Length: {raw_size!r}"
        ) from error
    if byte_count <= 0:
        raise AcquisitionError("official mirror returned an empty image")
    return RemoteObject(
        byte_count=byte_count,
        md5_hex=_simple_etag(headers.get("ETag")),
    )


def _open_request(
    url: str,
    *,
    method: str,
    headers: dict[str, str] | None,
    timeout_seconds: float,
) -> Any:
    request = urllib.request.Request(
        url,
        method=method,
        headers=headers or {},
    )
    return urllib.request.urlopen(request, timeout=timeout_seconds)


def _head_remote(url: str, *, timeout_seconds: float) -> RemoteObject:
    with _open_request(
        url,
        method="HEAD",
        headers=None,
        timeout_seconds=timeout_seconds,
    ) as response:
        return _remote_object_from_headers(response.headers)


def _verify_against_remote(path: Path, remote: RemoteObject) -> str:
    actual_size = path.stat().st_size
    if actual_size != remote.byte_count:
        raise AcquisitionError(
            f"size mismatch for {path.name}: "
            f"expected={remote.byte_count} actual={actual_size}"
        )
    actual_md5 = _md5_file(path)
    if actual_md5 != remote.md5_hex:
        raise AcquisitionError(
            f"mirror MD5 mismatch for {path.name}: "
            f"expected={remote.md5_hex} actual={actual_md5}"
        )
    return actual_md5


def _download_once(
    *,
    image_id: str,
    url: str,
    final_path: Path,
    timeout_seconds: float,
) -> tuple[str, RemoteObject, str]:
    """Download or reuse one file. Only verified partials become final files."""

    if final_path.exists():
        if not final_path.is_file():
            raise AcquisitionError(f"image destination is not a file: {final_path}")
        remote = _head_remote(url, timeout_seconds=timeout_seconds)
        return "reused_verified", remote, _verify_against_remote(final_path, remote)

    part_path = final_path.with_suffix(f"{final_path.suffix}.part")
    existing_bytes = part_path.stat().st_size if part_path.exists() else 0
    remote: RemoteObject | None = None
    if existing_bytes:
        remote = _head_remote(url, timeout_seconds=timeout_seconds)
        if existing_bytes > remote.byte_count:
            raise AcquisitionError(
                f"partial file is larger than the mirror object: {part_path}"
            )
        if existing_bytes == remote.byte_count:
            digest = _verify_against_remote(part_path, remote)
            os.replace(part_path, final_path)
            return "resumed_verified", remote, digest

    request_headers = (
        {"Range": f"bytes={existing_bytes}-"} if existing_bytes else {}
    )
    with _open_request(
        url,
        method="GET",
        headers=request_headers,
        timeout_seconds=timeout_seconds,
    ) as response:
        status = getattr(response, "status", response.getcode())
        if existing_bytes:
            if status != 206:
                raise AcquisitionError(
                    f"mirror did not honor byte-range resume for {image_id}"
                )
            content_range = response.headers.get("Content-Range", "")
            expected_prefix = f"bytes {existing_bytes}-"
            if not content_range.startswith(expected_prefix):
                raise AcquisitionError(
                    f"unexpected Content-Range for {image_id}: {content_range!r}"
                )
            if remote is None:
                raise AssertionError("resume requires a HEAD response")
            expected_suffix = f"/{remote.byte_count}"
            if not content_range.endswith(expected_suffix):
                raise AcquisitionError(
                    f"Content-Range total changed for {image_id}: "
                    f"{content_range!r}"
                )
            if _simple_etag(response.headers.get("ETag")) != remote.md5_hex:
                raise AcquisitionError(
                    f"mirror ETag changed during resume for {image_id}"
                )
        else:
            if status != 200:
                raise AcquisitionError(
                    f"unexpected HTTP status for {image_id}: {status}"
                )
            remote = _remote_object_from_headers(response.headers)

        mode = "ab" if part_path.exists() else "xb"
        with part_path.open(mode) as target:
            while chunk := response.read(COPY_CHUNK_SIZE):
                target.write(chunk)
            target.flush()
            os.fsync(target.fileno())

    if remote is None:
        raise AssertionError("download did not resolve remote metadata")
    digest = _verify_against_remote(part_path, remote)
    os.replace(part_path, final_path)
    return (
        "resumed_download" if existing_bytes else "downloaded",
        remote,
        digest,
    )


def _download_with_retries(
    *,
    image_id: str,
    url: str,
    final_path: Path,
    timeout_seconds: float,
    retries: int,
) -> tuple[str, RemoteObject, str]:
    transient_errors = (
        urllib.error.URLError,
        TimeoutError,
        ConnectionError,
        http.client.IncompleteRead,
        http.client.RemoteDisconnected,
        socket.timeout,
    )
    for attempt in range(retries + 1):
        try:
            return _download_once(
                image_id=image_id,
                url=url,
                final_path=final_path,
                timeout_seconds=timeout_seconds,
            )
        except transient_errors:
            if attempt == retries:
                raise
            time.sleep(min(2**attempt, 8))
    raise AssertionError("retry loop did not return or raise")


def _inspect_image(
    *,
    image_id: str,
    relative_path: str,
    status: str,
    path: Path,
    remote: RemoteObject,
    file_md5: str,
) -> AcquiredImage:
    from PIL import Image

    with Image.open(path) as image:
        raw_width, raw_height = image.size
        orientation = int(image.getexif().get(EXIF_ORIENTATION_TAG, 1))
    visual_width, visual_height = visually_oriented_size(path)
    return AcquiredImage(
        image_id=image_id,
        relative_path=relative_path,
        status=status,
        byte_count=remote.byte_count,
        mirror_etag=remote.md5_hex,
        file_md5=file_md5,
        sha256=sha256_file(path),
        raw_width=raw_width,
        raw_height=raw_height,
        visual_width=visual_width,
        visual_height=visual_height,
        exif_orientation=orientation,
    )


def _load_selection(
    selection_directory: Path,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    metadata_path = selection_directory / "selected-source-metadata.csv"
    ids_path = selection_directory / "image-ids.txt"
    report_path = selection_directory / "selection-report.json"
    for path in (metadata_path, ids_path, report_path):
        if not path.is_file():
            raise AcquisitionError(f"selection artifact is missing: {path}")

    with metadata_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "ImageID",
            "Author",
            "License",
            "OriginalMD5",
            "OriginalSize",
            "OriginalURL",
            "OriginalLandingURL",
        }
        fields = set(reader.fieldnames or ())
        missing_fields = sorted(required - fields)
        if missing_fields:
            raise AcquisitionError(
                f"selected metadata is missing fields: {missing_fields}"
            )
        rows = list(reader)

    metadata_by_id: dict[str, dict[str, str]] = {}
    for row in rows:
        image_id = row["ImageID"].strip().lower()
        if not IMAGE_ID_PATTERN.fullmatch(image_id):
            raise AcquisitionError(f"unsafe Open Images ID: {image_id!r}")
        if image_id in metadata_by_id:
            raise AcquisitionError(f"duplicate metadata ImageID: {image_id}")
        if not row["Author"].strip():
            raise AcquisitionError(f"missing author for ImageID {image_id}")
        if not row["License"].strip().startswith(
            "https://creativecommons.org/licenses/by/2.0"
        ):
            raise AcquisitionError(f"unapproved license for ImageID {image_id}")
        row["ImageID"] = image_id
        metadata_by_id[image_id] = row

    selected_ids: list[str] = []
    with ids_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            value = line.strip()
            match = re.fullmatch(r"train/([0-9a-f]{16})", value)
            if match is None:
                raise AcquisitionError(
                    f"invalid image ID line {line_number}: {value!r}"
                )
            selected_ids.append(match.group(1))
    if len(selected_ids) != len(set(selected_ids)):
        raise AcquisitionError("image-ids.txt contains duplicate entries")
    if set(selected_ids) != set(metadata_by_id):
        raise AcquisitionError(
            "selected metadata and image-ids.txt do not contain identical IDs"
        )

    with report_path.open("r", encoding="utf-8") as handle:
        selection_report = json.load(handle)
    expected_count = int(selection_report["selected_unique_image_count"])
    if expected_count != len(selected_ids):
        raise AcquisitionError(
            f"selection count mismatch: report={expected_count} "
            f"metadata={len(selected_ids)}"
        )
    return [metadata_by_id[item] for item in sorted(selected_ids)], selection_report


MANIFEST_FIELDS = (
    "ImageID",
    "RelativePath",
    "Width",
    "Height",
    "GroupID",
    "SHA256",
    "Author",
    "License",
    "OriginalLandingURL",
    "OriginalURL",
    "OriginalSize",
    "OriginalMD5",
    "OriginalMD5Hex",
    "OriginalRotation",
    "MirrorURL",
    "MirrorETag",
    "MirrorBytes",
    "FileMD5",
    "RawWidth",
    "RawHeight",
    "EXIFOrientation",
)


def acquire_open_images_training_images(
    *,
    selection_directory: str | Path,
    destination: str | Path,
    mirror_base_url: str = DEFAULT_MIRROR_BASE_URL,
    workers: int = 8,
    retries: int = 5,
    timeout_seconds: float = 60,
) -> dict[str, Any]:
    """Acquire every selected image and write a canonical attribution manifest."""

    if workers <= 0:
        raise ValueError("workers must be positive")
    if retries < 0:
        raise ValueError("retries cannot be negative")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    selection = Path(selection_directory)
    output = Path(destination)
    manifest_path = output / "acquired-images.csv"
    report_path = output / "acquisition-report.json"
    if manifest_path.exists() or report_path.exists():
        raise FileExistsError(
            f"completed acquisition artifacts already exist in {output}"
        )
    images_directory = output / "images" / "train"
    images_directory.mkdir(parents=True, exist_ok=True)

    selected_rows, selection_report = _load_selection(selection)
    row_by_id = {row["ImageID"]: row for row in selected_rows}
    base_url = mirror_base_url.rstrip("/")
    print(
        f"Acquiring {len(selected_rows):,} approved Open Images files "
        f"with {workers} workers",
        flush=True,
    )

    acquired: dict[str, AcquiredImage] = {}
    failures: list[tuple[str, str]] = []

    def acquire_one(row: dict[str, str]) -> AcquiredImage:
        image_id = row["ImageID"]
        relative_path = f"train/{image_id}.jpg"
        path = images_directory / f"{image_id}.jpg"
        url = f"{base_url}/train/{image_id}.jpg"
        status, remote, file_md5 = _download_with_retries(
            image_id=image_id,
            url=url,
            final_path=path,
            timeout_seconds=timeout_seconds,
            retries=retries,
        )
        return _inspect_image(
            image_id=image_id,
            relative_path=relative_path,
            status=status,
            path=path,
            remote=remote,
            file_md5=file_md5,
        )

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(acquire_one, row): row["ImageID"]
            for row in selected_rows
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            image_id = futures[future]
            try:
                acquired[image_id] = future.result()
            except Exception as error:
                failures.append(
                    (image_id, f"{type(error).__name__}: {error}")
                )
            if (
                completed == 1
                or completed % 25 == 0
                or completed == len(futures)
            ):
                print(
                    f"Processed {completed:,}/{len(futures):,}; "
                    f"verified={len(acquired):,}; failed={len(failures):,}",
                    flush=True,
                )

    if failures:
        examples = "; ".join(
            f"{image_id}: {detail}" for image_id, detail in failures[:10]
        )
        raise AcquisitionError(
            f"{len(failures)} image acquisition(s) failed; "
            f"verified files and partial downloads were preserved. {examples}"
        )
    if set(acquired) != set(row_by_id):
        raise AcquisitionError("acquisition results do not exactly cover selection")

    status_counts = Counter(item.status for item in acquired.values())
    orientation_counts = Counter(
        str(item.exif_orientation) for item in acquired.values()
    )
    license_counts = Counter(
        row["License"].strip() for row in selected_rows
    )
    missing_original_md5 = sum(
        _decode_original_md5(row.get("OriginalMD5", "")) is None
        for row in selected_rows
    )

    temporary_manifest = output / f".acquired-images.csv.part-{os.getpid()}"
    with temporary_manifest.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        for image_id in sorted(acquired):
            row = row_by_id[image_id]
            item = acquired[image_id]
            writer.writerow(
                {
                    "ImageID": image_id,
                    "RelativePath": item.relative_path,
                    "Width": item.visual_width,
                    "Height": item.visual_height,
                    "GroupID": f"open-images-v7-waste-subset:{image_id}",
                    "SHA256": item.sha256,
                    "Author": row["Author"].strip(),
                    "License": row["License"].strip(),
                    "OriginalLandingURL": row["OriginalLandingURL"].strip(),
                    "OriginalURL": row["OriginalURL"].strip(),
                    "OriginalSize": row["OriginalSize"].strip(),
                    "OriginalMD5": row["OriginalMD5"].strip(),
                    "OriginalMD5Hex": (
                        _decode_original_md5(row["OriginalMD5"]) or ""
                    ),
                    "OriginalRotation": row.get("Rotation", "").strip(),
                    "MirrorURL": f"{base_url}/train/{image_id}.jpg",
                    "MirrorETag": item.mirror_etag,
                    "MirrorBytes": item.byte_count,
                    "FileMD5": item.file_md5,
                    "RawWidth": item.raw_width,
                    "RawHeight": item.raw_height,
                    "EXIFOrientation": item.exif_orientation,
                }
            )

    report: dict[str, Any] = {
        "schema_version": "1.0",
        "source": "open-images-v7-waste-subset",
        "split": "train",
        "ok": True,
        "requested_image_count": len(selected_rows),
        "verified_image_count": len(acquired),
        "status_counts": dict(sorted(status_counts.items())),
        "actual_mirror_bytes": sum(
            item.byte_count for item in acquired.values()
        ),
        "actual_mirror_gib": round(
            sum(item.byte_count for item in acquired.values()) / (1024**3),
            3,
        ),
        "mirror": {
            "base_url": base_url,
            "integrity_method": "single-part-s3-etag-md5",
        },
        "attribution": {
            "license_counts": dict(sorted(license_counts.items())),
            "missing_author_count": sum(
                not row["Author"].strip() for row in selected_rows
            ),
            "missing_or_invalid_original_md5_count": missing_original_md5,
        },
        "image_decode": {
            "failure_count": 0,
            "exif_orientation_counts": dict(
                sorted(orientation_counts.items())
            ),
            "visually_transposed_count": sum(
                (item.raw_width, item.raw_height)
                != (item.visual_width, item.visual_height)
                for item in acquired.values()
            ),
        },
        "selection": {
            "selected_box_counts": selection_report["selected_box_counts"],
            "selected_image_counts_by_class": selection_report[
                "selected_image_counts_by_class"
            ],
            "selection_report_sha256": metadata_sha256_file(
                selection / "selection-report.json"
            ),
            "selected_metadata_sha256": metadata_sha256_file(
                selection / "selected-source-metadata.csv"
            ),
            "image_ids_sha256": metadata_sha256_file(
                selection / "image-ids.txt"
            ),
        },
    }
    report["manifest_sha256"] = metadata_sha256_file(temporary_manifest)

    temporary_report = output / f".acquisition-report.json.part-{os.getpid()}"
    with temporary_report.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")

    if manifest_path.exists() or report_path.exists():
        raise FileExistsError(
            f"refusing to overwrite completed acquisition in {output}"
        )
    os.replace(temporary_report, report_path)
    os.replace(temporary_manifest, manifest_path)
    return report
