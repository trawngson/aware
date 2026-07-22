"""Exact and perceptual duplicate helpers for use on VAST."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Mapping


def sha256_file(path: str | Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def difference_hash(path: str | Path, *, hash_size: int = 8) -> str:
    """Return a small dHash. Pillow is imported only when this check is run."""

    from PIL import Image

    with Image.open(path) as image:
        grayscale = image.convert("L").resize((hash_size + 1, hash_size))
        pixels = list(grayscale.getdata())
    bits = []
    row_width = hash_size + 1
    for row in range(hash_size):
        start = row * row_width
        bits.extend(
            pixels[start + column] > pixels[start + column + 1]
            for column in range(hash_size)
        )
    value = sum(int(bit) << index for index, bit in enumerate(bits))
    return f"{value:0{hash_size * hash_size // 4}x}"


def hamming_distance(left: str, right: str) -> int:
    if len(left) != len(right):
        raise ValueError("perceptual hashes must have equal length")
    return (int(left, 16) ^ int(right, 16)).bit_count()


def exact_duplicate_groups(hashes: Mapping[str, str]) -> dict[str, str]:
    members: dict[str, list[str]] = defaultdict(list)
    for image_id, digest in hashes.items():
        members[digest].append(image_id)
    groups: dict[str, str] = {}
    for digest, image_ids in members.items():
        if len(image_ids) > 1:
            group_id = f"exact:{digest}"
            for image_id in image_ids:
                groups[image_id] = group_id
    return groups


def perceptual_duplicate_groups(
    hashes: Mapping[str, str],
    *,
    maximum_distance: int = 5,
) -> dict[str, str]:
    """Cluster small inventories using deterministic connected components."""

    image_ids = sorted(hashes)
    parent = {image_id: image_id for image_id in image_ids}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    if not image_ids:
        return {}
    bit_count = len(next(iter(hashes.values()))) * 4
    if maximum_distance < 0:
        raise ValueError("maximum_distance cannot be negative")
    if any(len(value) * 4 != bit_count for value in hashes.values()):
        raise ValueError("perceptual hashes must have equal length")

    # Split each hash into d+1 segments. Any pair within Hamming distance d
    # must share at least one exact segment, which avoids an all-pairs scan.
    segment_count = min(maximum_distance + 1, bit_count)
    buckets: dict[tuple[int, int], list[str]] = defaultdict(list)
    for image_id in image_ids:
        value = int(hashes[image_id], 16)
        for segment in range(segment_count):
            start = segment * bit_count // segment_count
            end = (segment + 1) * bit_count // segment_count
            width = end - start
            segment_value = (value >> start) & ((1 << width) - 1)
            buckets[(segment, segment_value)].append(image_id)

    candidates: set[tuple[str, str]] = set()
    for members in buckets.values():
        for index, left in enumerate(members):
            for right in members[index + 1 :]:
                candidates.add((min(left, right), max(left, right)))
    for left, right in sorted(candidates):
        if hamming_distance(hashes[left], hashes[right]) <= maximum_distance:
            union(left, right)

    components: dict[str, list[str]] = defaultdict(list)
    for image_id in image_ids:
        components[find(image_id)].append(image_id)
    result: dict[str, str] = {}
    for members in components.values():
        if len(members) > 1:
            group_id = f"perceptual:{members[0]}"
            for image_id in members:
                result[image_id] = group_id
    return result
