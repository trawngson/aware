from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from src.open_images_acquisition import (
    AcquisitionError,
    RemoteObject,
    acquire_open_images_training_images,
)


def jpeg_bytes(color: tuple[int, int, int]) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (32, 24), color=color).save(output, format="JPEG")
    return output.getvalue()


class FakeResponse:
    def __init__(
        self,
        payload: bytes,
        *,
        status: int,
        etag: str,
        content_range: str | None = None,
    ) -> None:
        self.payload = io.BytesIO(payload)
        self.status = status
        self.headers = {
            "Content-Length": str(len(payload)),
            "ETag": f'"{etag}"',
        }
        if content_range is not None:
            self.headers["Content-Range"] = content_range

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return

    def getcode(self) -> int:
        return self.status

    def read(self, size: int = -1) -> bytes:
        return self.payload.read(size)


class FakeMirror:
    def __init__(self, payloads: dict[str, bytes]) -> None:
        self.payloads = payloads

    def remote(self, image_id: str) -> RemoteObject:
        payload = self.payloads[image_id]
        return RemoteObject(
            byte_count=len(payload),
            md5_hex=hashlib.md5(
                payload, usedforsecurity=False
            ).hexdigest(),
        )

    def head(self, url: str, *, timeout_seconds: float) -> RemoteObject:
        return self.remote(Path(url).stem)

    def open(
        self,
        url: str,
        *,
        method: str,
        headers: dict[str, str] | None,
        timeout_seconds: float,
    ) -> FakeResponse:
        self.assert_get(method)
        image_id = Path(url).stem
        payload = self.payloads[image_id]
        remote = self.remote(image_id)
        range_header = (headers or {}).get("Range")
        if range_header is None:
            return FakeResponse(
                payload,
                status=200,
                etag=remote.md5_hex,
            )
        start = int(range_header.removeprefix("bytes=").removesuffix("-"))
        return FakeResponse(
            payload[start:],
            status=206,
            etag=remote.md5_hex,
            content_range=f"bytes {start}-{len(payload) - 1}/{len(payload)}",
        )

    def assert_get(self, method: str) -> None:
        if method != "GET":
            raise AssertionError(f"unexpected fake request method: {method}")


def write_selection(root: Path, image_ids: list[str]) -> Path:
    selection = root / "selection"
    selection.mkdir()
    metadata = selection / "selected-source-metadata.csv"
    fields = (
        "ImageID",
        "Author",
        "License",
        "OriginalMD5",
        "OriginalSize",
        "OriginalURL",
        "OriginalLandingURL",
        "Rotation",
    )
    original_digest = hashlib.md5(
        b"original", usedforsecurity=False
    ).digest()
    with metadata.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for image_id in image_ids:
            writer.writerow(
                {
                    "ImageID": image_id,
                    "Author": f"Author {image_id}",
                    "License": "https://creativecommons.org/licenses/by/2.0/",
                    "OriginalMD5": base64.b64encode(original_digest).decode(),
                    "OriginalSize": "1000",
                    "OriginalURL": f"https://example.invalid/{image_id}.jpg",
                    "OriginalLandingURL": (
                        f"https://example.invalid/photos/{image_id}"
                    ),
                    "Rotation": "0",
                }
            )
    (selection / "image-ids.txt").write_text(
        "".join(f"train/{image_id}\n" for image_id in image_ids),
        encoding="utf-8",
    )
    (selection / "selection-report.json").write_text(
        json.dumps(
            {
                "selected_unique_image_count": len(image_ids),
                "selected_box_counts": {
                    "Plastic bag": len(image_ids),
                    "Tin can": len(image_ids),
                },
                "selected_image_counts_by_class": {
                    "Plastic bag": len(image_ids),
                    "Tin can": len(image_ids),
                },
            }
        ),
        encoding="utf-8",
    )
    return selection


class OpenImagesAcquisitionTests(unittest.TestCase):
    def test_downloads_resumes_verifies_decodes_and_writes_manifest(self) -> None:
        image_ids = ["0000000000000001", "0000000000000002"]
        payloads = {
            image_ids[0]: jpeg_bytes((255, 0, 0)),
            image_ids[1]: jpeg_bytes((0, 255, 0)),
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            selection = write_selection(root, image_ids)
            destination = root / "acquisition"
            images = destination / "images" / "train"
            images.mkdir(parents=True)
            partial = images / f"{image_ids[0]}.jpg.part"
            partial.write_bytes(payloads[image_ids[0]][:100])

            mirror = FakeMirror(payloads)
            with patch(
                "src.open_images_acquisition._head_remote",
                side_effect=mirror.head,
            ), patch(
                "src.open_images_acquisition._open_request",
                side_effect=mirror.open,
            ):
                report = acquire_open_images_training_images(
                    selection_directory=selection,
                    destination=destination,
                    mirror_base_url="https://mirror.invalid",
                    workers=2,
                    retries=0,
                )

            self.assertEqual(report["verified_image_count"], 2)
            self.assertEqual(
                report["status_counts"],
                {"downloaded": 1, "resumed_download": 1},
            )
            self.assertEqual(report["image_decode"]["failure_count"], 0)
            self.assertFalse(partial.exists())

            with (destination / "acquired-images.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["ImageID"] for row in rows], image_ids)
            self.assertEqual(rows[0]["Width"], "32")
            self.assertEqual(rows[0]["Height"], "24")
            self.assertEqual(rows[0]["FileMD5"], rows[0]["MirrorETag"])
            self.assertEqual(rows[0]["RelativePath"], f"train/{image_ids[0]}.jpg")
            self.assertEqual(rows[0]["EXIFOrientation"], "1")

    def test_existing_file_with_wrong_mirror_md5_fails_without_overwrite(self) -> None:
        image_id = "0000000000000001"
        payload = jpeg_bytes((0, 0, 255))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            selection = write_selection(root, [image_id])
            destination = root / "acquisition"
            image_path = destination / "images" / "train" / f"{image_id}.jpg"
            image_path.parent.mkdir(parents=True)
            image_path.write_bytes(b"do not overwrite")

            mirror = FakeMirror({image_id: payload})
            with patch(
                "src.open_images_acquisition._head_remote",
                side_effect=mirror.head,
            ):
                with self.assertRaisesRegex(
                    AcquisitionError,
                    "image acquisition.*failed",
                ):
                    acquire_open_images_training_images(
                        selection_directory=selection,
                        destination=destination,
                        mirror_base_url="https://mirror.invalid",
                        workers=1,
                        retries=0,
                    )

            self.assertEqual(image_path.read_bytes(), b"do not overwrite")
            self.assertFalse((destination / "acquired-images.csv").exists())


if __name__ == "__main__":
    unittest.main()
