"""Render exact exported CAD meshes and a self-contained offline inspector."""

from pathlib import Path
import argparse
import json
import os

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "v2"
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache/matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(ROOT / ".cache"))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from PIL import Image


def render(meshes, name, mode):
    # CPU depth rasterization avoids a GUI/GPU dependency and correctly occludes
    # hollow CAD surfaces; painter-sorted triangles produce misleading artifacts.
    faces, colors = [], []
    key = np.array([.5, -.7, 1.0]); key /= np.linalg.norm(key)
    fill = np.array([-.8, .3, .5]); fill /= np.linalg.norm(fill)
    angle, elevation = np.radians(-55), np.radians(17)
    view = (np.array([0., 0., 1.]) if mode == "plan" else
            np.array([np.cos(elevation) * np.cos(angle),
                      np.cos(elevation) * np.sin(angle), np.sin(elevation)]))
    right = np.array([1., 0., 0.]) if mode == "plan" else np.cross([0, 0, 1], view)
    right /= np.linalg.norm(right)
    up = np.cross(view, right)
    basis = np.stack([right, up, view], axis=1)
    for mesh in meshes:
        if mode in ("internals", "exploded") and mesh["group"] == "shell":
            continue
        if mode == "plan" and mesh["group"] not in ("liners", "labels", "shell", "fill_sensors"):
            continue
        offset = mesh["explode"] if mode == "exploded" else (0, 0, 0)
        vertices = np.asarray(mesh["vertices"]) + offset
        triangles = vertices[np.asarray(mesh["triangles"])]
        normal = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
        normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-12)
        normal[normal @ view < 0] *= -1
        brightness = .3 + .52 * np.maximum(0, normal @ key) + .20 * np.maximum(0, normal @ fill)
        faces.extend(triangles @ basis)
        colors.extend(np.clip(brightness[:, None] * np.asarray(mesh["color"]), 0, 1))
    faces = np.asarray(faces)
    colors = np.uint8(np.clip(np.asarray(colors) * 255, 0, 255))
    n = 1500
    xy = faces[:, :, :2].reshape(-1, 2)
    lo, hi = xy.min(axis=0), xy.max(axis=0)
    center = (lo + hi) / 2
    scale = n * .85 / max(hi - lo)
    faces[:, :, 0] = (faces[:, :, 0] - center[0]) * scale + n / 2
    faces[:, :, 1] = n / 2 - (faces[:, :, 1] - center[1]) * scale
    rgb = np.empty((n, n, 3), dtype=np.uint8); rgb[:] = [246, 248, 246]
    depth = np.full((n, n), -np.inf)
    for triangle, color in zip(faces, colors):
        x0, y0, z0 = triangle[0]; x1, y1, z1 = triangle[1]; x2, y2, z2 = triangle[2]
        determinant = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(determinant) < 1e-8:
            continue
        xmin = max(0, int(np.floor(min(x0, x1, x2))))
        xmax = min(n - 1, int(np.ceil(max(x0, x1, x2))))
        ymin = max(0, int(np.floor(min(y0, y1, y2))))
        ymax = min(n - 1, int(np.ceil(max(y0, y1, y2))))
        if xmin > xmax or ymin > ymax:
            continue
        xs = np.arange(xmin, xmax + 1)[None, :] + .5
        ys = np.arange(ymin, ymax + 1)[:, None] + .5
        w0 = ((y1 - y2) * (xs - x2) + (x2 - x1) * (ys - y2)) / determinant
        w1 = ((y2 - y0) * (xs - x2) + (x0 - x2) * (ys - y2)) / determinant
        w2 = 1 - w0 - w1
        z = w0 * z0 + w1 * z1 + w2 * z2
        buffer = depth[ymin:ymax + 1, xmin:xmax + 1]
        mask = (w0 >= -1e-7) & (w1 >= -1e-7) & (w2 >= -1e-7) & (z > buffer)
        buffer[mask] = z[mask]
        rgb[ymin:ymax + 1, xmin:xmax + 1][mask] = color
    Image.fromarray(rgb).resize((1120, 1120), Image.Resampling.LANCZOS).save(OUTPUT / name)


def sheet(dimensions):
    fig = plt.figure(figsize=(15, 12), facecolor="#f6f8f6")
    revision = dimensions.get("revision", "v1")
    fig.text(.04, .957, f"SMART SORTING BIN · {revision.upper()}", fontsize=27, weight="bold", color="#233337")
    subtitle = ("Rear mast · one tilting plate · four separate compartments · category labels blank"
                if revision == "v2" else "Physical CAD concept · four separate compartments · category labels blank")
    fig.text(.04, .923, subtitle,
             fontsize=12, color="#647174")
    panels = [(.015, .485, "assembled.png", "01  ASSEMBLED"),
              (.505, .485, "internals.png", "02  OUTER SHELL HIDDEN"),
              (.015, .045, "plan.png", "03  TOP PLAN / IR SENSOR POSITIONS"),
              (.505, .045, "exploded.png", "04  EXPLODED / SHELL HIDDEN")]
    for x, y, filename, title in panels:
        ax = fig.add_axes([x, y, .48, .405])
        ax.imshow(mpimg.imread(OUTPUT / filename))
        ax.axis("off")
        fig.text(x + .035, y + .404, title, fontsize=11, weight="bold", color="#34484e")
    text = (f"BODY Ø{dimensions['body_diameter_mm']:g} mm    ·    "
            f"RIM {dimensions['rim_height_mm']:g} mm    ·    "
            f"OVERALL {dimensions['overall_height_mm']:g} mm    ·    "
            f"CANOPY Ø{dimensions['canopy_diameter_mm']:g} mm")
    fig.text(.05, .025, text, fontsize=11, color="#233337")
    fig.savefig(OUTPUT / "preview.png", dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)


def main():
    global OUTPUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--template", type=Path, default=ROOT / "cad/viewer_v2_template.html")
    args = parser.parse_args()
    OUTPUT = args.output
    meshes = json.loads((OUTPUT / "mesh.json").read_text())
    dimensions = json.loads((OUTPUT / "dimensions.json").read_text())
    for filename, mode in [("assembled.png", "assembled"), ("internals.png", "internals"),
                           ("plan.png", "plan"), ("exploded.png", "exploded")]:
        print(f"Rendering {mode}…", flush=True)
        render(meshes, filename, mode)
    sheet(dimensions)
    if dimensions.get("revision") == "v2":
        tilt_meshes = json.loads((OUTPUT / "tilt_mesh_4.json").read_text())
        render(tilt_meshes, "tilted_to_sub_bin_4.png", "assembled")
    template = args.template.read_text()
    template = template.replace("__MESH_DATA__", json.dumps(meshes, separators=(",", ":")))
    template = template.replace("__DIMENSIONS__", json.dumps(dimensions))
    (OUTPUT / "viewer.html").write_text(template)
    print("Preview and offline viewer ready.", flush=True)


if __name__ == "__main__":
    main()
