"""Cuts the A3 sheets out of the full-size panel PDFs.

Usage: python3 tile.py sheets.json out_dir result.pdf
Each sheet gets: a blank A3 page, the panel artwork clipped to the sheet's
window and moved into place, then the crop marks and labels on top.
"""
import json
import sys

from pypdf import PdfReader, PdfWriter, PageObject, Transformation
from pypdf.generic import RectangleObject

MM = 72 / 25.4
PANEL_FILES = {"left": "panel-left-400x900mm.pdf", "centre": "panel-centre-800x900mm.pdf", "right": "panel-right-400x900mm.pdf"}

job, out_dir, result = sys.argv[1:4]
sheets = json.load(open(job))
writer = PdfWriter()
# One reader per panel, so its images are written to the result only once.
readers = {}
for s in sheets:
    f = {k: float(v) for k, v in s.items() if k not in ("panel", "marks")}
    sw, sh = f["sw"] * MM, f["sh"] * MM
    page = PageObject.create_blank_page(width=sw, height=sh)

    if s["panel"] not in readers:
        readers[s["panel"]] = PdfReader(f"{out_dir}/{PANEL_FILES[s['panel']]}")
    panel = readers[s["panel"]].pages[0]
    ph = float(panel.mediabox.height)
    # Window in panel coordinates (PDF origin is bottom-left).
    x1 = f["col"] * f["cw"] * MM
    top = ph - f["row"] * f["ch"] * MM
    win = RectangleObject([x1, top - f["winH"] * MM, x1 + f["winW"] * MM, top])
    panel.cropbox = win  # pypdf clips merged content to the source cropbox
    tx = f["x0"] * MM - x1
    ty = (sh - f["y0"] * MM) - top
    page.merge_transformed_page(panel, Transformation().translate(tx, ty))

    marks = PdfReader(s["marks"]).pages[0]
    page.merge_page(marks)
    writer.add_page(page)

writer.compress_identical_objects(remove_duplicates=True, remove_unreferenced=True)
with open(result, "wb") as fh:
    writer.write(fh)
print(f"Wrote {result} ({len(sheets)} sheets)")
