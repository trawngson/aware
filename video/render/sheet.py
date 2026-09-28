"""Combine preview PNGs into a labelled contact sheet: python3 sheet.py dir out.jpg [cols]"""
import sys, glob, os
from PIL import Image, ImageDraw
d, out = sys.argv[1], sys.argv[2]
cols = int(sys.argv[3]) if len(sys.argv) > 3 else 3
files = sorted(glob.glob(os.path.join(d, "t*.png")), key=lambda f: float(os.path.basename(f)[1:-4]))
W, H = 640, 360
rows = (len(files) + cols - 1) // cols
sheet = Image.new("RGB", (cols * W, rows * H), "black")
for i, f in enumerate(files):
    im = Image.open(f).convert("RGB").resize((W, H), Image.LANCZOS)
    dr = ImageDraw.Draw(im)
    dr.rectangle((0, 0, 70, 22), fill="black")
    dr.text((5, 5), os.path.basename(f)[1:-4], fill="yellow")
    sheet.paste(im, ((i % cols) * W, (i // cols) * H))
sheet.save(out, quality=88)
