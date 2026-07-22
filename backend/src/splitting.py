"""Deterministic group-aware splitting and leakage verification."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .canonical_data import CanonicalImage


@dataclass(frozen=True)
class LeakageViolation:
    relationship: str
    key: str
    splits: tuple[str, ...]


def _unit_interval(seed: int, group_id: str) -> float:
    digest = hashlib.sha256(f"{seed}:{group_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def _connected_groups(
    images: Sequence[CanonicalImage],
    duplicate_groups: Mapping[str, str],
) -> dict[str, list[str]]:
    parent = {image.image_id: image.image_id for image in images}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    relationships: dict[tuple[str, str], list[str]] = defaultdict(list)
    for image in images:
        relationships[("capture", image.group_id)].append(image.image_id)
        if image.exact_hash:
            relationships[("exact", image.exact_hash)].append(image.image_id)
        duplicate_group = duplicate_groups.get(image.image_id)
        if duplicate_group:
            relationships[("perceptual", duplicate_group)].append(image.image_id)
    for members in relationships.values():
        for image_id in members[1:]:
            union(members[0], image_id)

    components: dict[str, list[str]] = defaultdict(list)
    for image in images:
        components[find(image.image_id)].append(image.image_id)
    return dict(components)


def assign_group_aware_splits(
    images: Sequence[CanonicalImage],
    *,
    seed: int,
    ratios: Mapping[str, float] | None = None,
    duplicate_groups: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Assign related images together using a stable hash of each component."""

    selected_ratios = dict(ratios or {"train": 0.8, "val": 0.2})
    if not selected_ratios or any(value <= 0 for value in selected_ratios.values()):
        raise ValueError("split ratios must be positive")
    if abs(sum(selected_ratios.values()) - 1.0) > 1e-9:
        raise ValueError("split ratios must sum to 1")
    image_ids = [image.image_id for image in images]
    if len(set(image_ids)) != len(image_ids):
        raise ValueError("image IDs must be unique before splitting")

    boundaries: list[tuple[str, float]] = []
    cumulative = 0.0
    for split, ratio in selected_ratios.items():
        cumulative += ratio
        boundaries.append((split, cumulative))

    assignments: dict[str, str] = {}
    components = _connected_groups(images, duplicate_groups or {})
    for root, members in sorted(components.items()):
        value = _unit_interval(seed, root)
        split = boundaries[-1][0]
        for candidate, boundary in boundaries:
            if value < boundary:
                split = candidate
                break
        for image_id in members:
            assignments[image_id] = split
    return assignments


def find_leakage(
    images: Sequence[CanonicalImage],
    assignments: Mapping[str, str],
    *,
    duplicate_groups: Mapping[str, str] | None = None,
) -> tuple[LeakageViolation, ...]:
    relations: dict[tuple[str, str], set[str]] = defaultdict(set)
    duplicate_groups = duplicate_groups or {}
    for image in images:
        split = assignments[image.image_id]
        relations[("capture_group", image.group_id)].add(split)
        if image.exact_hash:
            relations[("exact_hash", image.exact_hash)].add(split)
        if image.image_id in duplicate_groups:
            relations[("perceptual_group", duplicate_groups[image.image_id])].add(split)
    return tuple(
        LeakageViolation(kind, key, tuple(sorted(splits)))
        for (kind, key), splits in sorted(relations.items())
        if len(splits) > 1
    )
