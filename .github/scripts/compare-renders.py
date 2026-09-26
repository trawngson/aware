#!/usr/bin/env python3
"""Compares render-check previews with a baseline run's previews.

Usage: compare-renders.py <baseline-dir> <current-dir>

Both directories hold <appearance>/NN-name.jpg files, as made by the render
check's "Make previews" step. For every current screenshot with a baseline of
the same name it prints how many pixels changed, and for screens that changed
noticeably a coarse map of where (one character per cell: '.' same, 'o' a
little, '#' a lot). The report goes to stdout and, when set, to
$GITHUB_STEP_SUMMARY. It only reports; it never fails the job, because map
tiles and animations differ a little between runs anyway.

JPEGs are turned into BMP with macOS's `sips`, so no Python packages are needed.
"""
import os
import struct
import subprocess
import sys
import tempfile

GRID_COLUMNS = 12
GRID_ROWS = 24
PIXEL_THRESHOLD = 40  # a channel difference above this counts as changed
REPORT_MAP_ABOVE = 0.5  # percent of changed pixels


def load_bmp(path):
    with open(path, "rb") as handle:
        data = handle.read()
    offset = struct.unpack_from("<I", data, 10)[0]
    width, height = struct.unpack_from("<ii", data, 18)
    bits = struct.unpack_from("<H", data, 28)[0]
    if bits not in (24, 32):
        raise ValueError(f"{path}: {bits}-bit BMP not supported")
    step = bits // 8
    row_size = (width * step + 3) & ~3
    top_down = height < 0
    height = abs(height)
    rows = []
    for y in range(height):
        source_row = y if top_down else height - 1 - y
        start = offset + source_row * row_size
        rows.append(data[start:start + width * step])
    return width, height, step, rows


def to_bmp(jpeg, directory):
    out = os.path.join(directory, os.path.basename(jpeg) + ".bmp")
    subprocess.run(["sips", "-s", "format", "bmp", jpeg, "--out", out],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out


def compare(baseline, current, directory):
    bw, bh, bstep, brows = load_bmp(to_bmp(baseline, directory))
    cw, ch, cstep, crows = load_bmp(to_bmp(current, directory))
    if (bw, bh) != (cw, ch):
        return None, f"size {bw}x{bh} -> {cw}x{ch}", []
    changed = 0
    cells = [[0] * GRID_COLUMNS for _ in range(GRID_ROWS)]
    cell_total = [[0] * GRID_COLUMNS for _ in range(GRID_ROWS)]
    for y in range(0, ch, 2):
        brow, crow = brows[y], crows[y]
        gy = min(y * GRID_ROWS // ch, GRID_ROWS - 1)
        for x in range(0, cw, 2):
            b = brow[x * bstep:x * bstep + 3]
            c = crow[x * cstep:x * cstep + 3]
            gx = min(x * GRID_COLUMNS // cw, GRID_COLUMNS - 1)
            cell_total[gy][gx] += 1
            if max(abs(b[0] - c[0]), abs(b[1] - c[1]), abs(b[2] - c[2])) > PIXEL_THRESHOLD:
                changed += 1
                cells[gy][gx] += 1
    sampled = sum(map(sum, cell_total))
    percent = 100.0 * changed / max(sampled, 1)
    grid = []
    for gy in range(GRID_ROWS):
        line = ""
        for gx in range(GRID_COLUMNS):
            share = cells[gy][gx] / max(cell_total[gy][gx], 1)
            line += "#" if share > 0.2 else "o" if share > 0.02 else "."
        grid.append(line)
    return percent, "", grid


def main():
    baseline_dir, current_dir = sys.argv[1], sys.argv[2]
    lines = ["### Screens compared with the baseline", "",
             "| Screen | Changed pixels |", "|---|---|"]
    maps = []
    with tempfile.TemporaryDirectory() as directory:
        for root, _, files in sorted(os.walk(current_dir)):
            for name in sorted(files):
                if not name.endswith(".jpg"):
                    continue
                current = os.path.join(root, name)
                relative = os.path.relpath(current, current_dir)
                baseline = os.path.join(baseline_dir, relative)
                if not os.path.exists(baseline):
                    lines.append(f"| {relative} | new screen |")
                    continue
                try:
                    percent, note, grid = compare(baseline, current, directory)
                except Exception as error:  # report and keep going
                    lines.append(f"| {relative} | error: {error} |")
                    continue
                if percent is None:
                    lines.append(f"| {relative} | {note} |")
                    continue
                lines.append(f"| {relative} | {percent:.2f}% |")
                if percent > REPORT_MAP_ABOVE:
                    maps.append((relative, grid))
    if maps:
        lines += ["", "Where they changed ('#' a lot, 'o' a little):"]
        for relative, grid in maps:
            lines += ["", f"{relative}", "```"] + grid + ["```"]
    report = "\n".join(lines)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as handle:
            handle.write(report + "\n")


if __name__ == "__main__":
    main()
