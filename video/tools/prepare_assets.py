"""Derive the video's images from the app's asset catalog.

Blurs are baked in here so the renderer never has to blur large layers per frame.
Run from the repository root: python3 video/tools/prepare_assets.py
"""
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "awareapp" / "Assets.xcassets"
OUT = ROOT / "video" / "assets" / "img"
OUT.mkdir(parents=True, exist_ok=True)


def square(img, size):
    s = min(img.size)
    left, top = (img.width - s) // 2, (img.height - s) // 2
    return img.crop((left, top, left + s, top + s)).resize((size, size), Image.LANCZOS)


forest = Image.open(SRC / "ForestBackground.imageset" / "ForestBackground.jpg").convert("RGB")
square(forest, 2112).save(OUT / "forest.jpg", quality=88, optimize=True)
square(forest, 1056).filter(ImageFilter.GaussianBlur(22)).resize((2112, 2112), Image.LANCZOS).save(
    OUT / "forest_blur.jpg", quality=86, optimize=True
)

projects = {
    "lamp": "RecycleProject1.imageset/CleanShot 2026-03-01 at 09.13.01@2x.png",
    "turtle": "recycleproject2.imageset/recycleproject2.jpg",
    "spiral": "RecycleProject3.imageset/CleanShot 2026-03-01 at 09.30.11@2x.png",
}
for name, rel in projects.items():
    square(Image.open(SRC / rel).convert("RGB"), 720).save(OUT / f"{name}.jpg", quality=90, optimize=True)

avatar = Image.open(SRC / "PlaceholderAvatar.imageset" / "9692405a4772c00b-sticker.png").convert("RGBA")
avatar.resize((320, 320), Image.LANCZOS).save(OUT / "avatar.png", optimize=True)

print("wrote", sorted(p.name for p in OUT.iterdir()))
