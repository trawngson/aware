#!/usr/bin/env python3
"""Builds the README's screenshots and GIFs from an iOS render check run.

Capture the README tour in both appearances with video, download the full-size
results, then build:

    gh workflow run ios-render-check.yml --ref <branch> -f steps=readme -f record_video=true
    gh run download <run-id> -n render -D render
    python3 .github/scripts/readme-media.py render

Everything is written to .github/readme/. Needs Pillow, numpy and ffmpeg (on
PATH, or `pip install imageio-ffmpeg`); with gifsicle and pngquant installed
the GIFs and PNGs come out smaller.

The screenshots are the tour's PNGs in a device frame. The GIFs are cut from
the recordings at the tour's steps (timeline.json), with a dot where each tap
lands and long pauses shortened.
"""

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".github" / "readme"
FOREST = ROOT / "awareapp/Assets.xcassets/ForestBackground.imageset/ForestBackground.jpg"
ICON = ROOT / "awareapp/Assets.xcassets/AppIcon.appiconset/AppIcon~ios-marketing.png"

# An iPhone Pro, in fractions of the screen's width.
BEZEL = 0.036
RIM = 0.009
CORNER = 0.148
ISLAND_WIDTH, ISLAND_HEIGHT, ISLAND_TOP = 0.313, 0.092, 0.027
RIM_COLOR = (74, 76, 78, 255)
BEZEL_COLOR = (10, 11, 11, 255)
SHADOW_COLOR = (7, 20, 13)

# Screenshots are 3× the screen's points.
POINT_SCALE = 3

STILL_WIDTH = 402      # screen width of the framed screenshots (2× at 201 pt)
GIF_WIDTH = 300        # screen width in the GIFs
DECODE_FPS = 60        # recordings are decoded at this rate, then sampled per GIF
TOUCH_MISSING_DELAY = 0.35  # when a tap's reaction can't be seen, assume this delay


@dataclass
class Still:
    """A framed screenshot, from a tour shot or a moment in the recording."""
    name: str
    shot: str = ""            # the tour's shot name
    at: str = ""              # or a time in the recording, see `Timeline.time`
    appearances: tuple = ("dark",)


@dataclass
class Clip:
    """A GIF cut from one appearance's recording between two tour steps."""
    name: str
    appearance: str
    start: str                # see `Timeline.time`
    end: str
    fps: int = 15
    max_still: float = 1.1    # longer pauses are shortened to this
    end_still: float = 1.6    # pause before the loop restarts
    fade: float = 0.3         # crossfade back to the first frame


STILLS = [
    Still("onboarding", shot="onboarding"),
    Still("home", shot="home"),
    Still("scan-live", at="tab:Scan@touch+2.2"),
    Still("scan-results", shot="scan-results"),
    Still("scan-guidance", shot="scan-guidance"),
    Still("waste-saved", shot="waste-saved"),
    Still("co2-saved", shot="co2-saved"),
    Still("recycling-map", shot="recycling-map"),
    Still("leaderboard", shot="leaderboard"),
    Still("more", shot="more"),
    Still("gallery", shot="gallery"),
    Still("post", shot="post"),
    Still("new-post", shot="new-post"),
]

CLIPS = [
    Clip("scan", "dark", start="tab:Scan@touch-0.5", end="shot:scan-shared@end-0.4", fps=15),
    Clip("home", "dark", start="tap:Got it@touch-0.6", end="scroll:up@end+1.0", fps=20),
    Clip("insights", "dark", start="tap:Waste Saved@touch-0.5", end="tap:Recycling Map@touch-0.4"),
    Clip("map", "light", start="tap:Recycling Map@touch-0.5", end="tap:All@end+1.2"),
    Clip("gallery", "dark", start="tab:Gallery@touch-0.5", end="tap:Share what you made@touch-0.4", fps=20),
    Clip("compose", "dark", start="tap:Share what you made@touch-0.5", end="tap:Cancel@end+0.6"),
]

# Light and Dark of these shots, revealed in turn.
THEME_SHOTS = ["recycling-map", "gallery"]

BANNER_SHOTS = ["onboarding", "home", "scan-results", "gallery", "recycling-map"]


# MARK: - ffmpeg

def find_ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("ffmpeg not found: install it, or `pip install imageio-ffmpeg`")


FFMPEG = find_ffmpeg()


def video_size(path):
    probe = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    match = re.search(r"Video: .*?, (\d{2,5})x(\d{2,5})", probe.stderr)
    if not match:
        sys.exit(f"Can't read the video size of {path}")
    return int(match.group(1)), int(match.group(2))


def decode(path, width, height, fps=DECODE_FPS, start=0.0, count=None):
    """Yields RGB frames at `fps`, frame k showing time start + k / fps."""
    command = [FFMPEG, "-v", "error"]
    if start:
        command += ["-ss", f"{start:.3f}"]
    command += ["-i", str(path), "-vf",
                f"fps=fps={fps}:start_time=0,scale={width}:{height}:flags=lanczos"]
    if count:
        command += ["-frames:v", str(count)]
    command += ["-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    process = subprocess.Popen(command, stdout=subprocess.PIPE)
    size = width * height * 3
    try:
        while True:
            data = process.stdout.read(size)
            if len(data) < size:
                break
            yield np.frombuffer(data, np.uint8).reshape(height, width, 3)
    finally:
        process.stdout.close()
        process.wait()


def encode_gif(frames, fps, path):
    """Writes RGBA frames as a looping GIF with a transparent background."""
    height, width = frames[0].shape[:2]
    palette = ("split[a][b];[a]palettegen=max_colors=255:reserve_transparent=1:stats_mode=full[p];"
               "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle:alpha_threshold=128")
    command = [FFMPEG, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba",
               "-s", f"{width}x{height}", "-framerate", str(fps), "-i", "-",
               "-lavfi", palette, "-loop", "0", str(path)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    for frame in frames:
        process.stdin.write(np.ascontiguousarray(frame).tobytes())
    process.stdin.close()
    if process.wait():
        sys.exit(f"ffmpeg failed writing {path}")
    if shutil.which("gifsicle"):
        subprocess.run(["gifsicle", "-b", "-O3", "--lossy=35", str(path)], check=True)


# MARK: - Device frame

def rounded_mask(size, box, radius, supersample=4):
    """An anti-aliased rounded rectangle mask."""
    width, height = size
    big = Image.new("L", (width * supersample, height * supersample), 0)
    x0, y0, x1, y1 = (v * supersample for v in box)
    ImageDraw.Draw(big).rounded_rectangle([x0, y0, x1 - 1, y1 - 1], radius=radius * supersample, fill=255)
    return big.resize(size, Image.LANCZOS)


class DeviceFrame:
    """Puts screens of one size in an iPhone frame, returning RGBA images."""

    def __init__(self, screen_width, screen_height):
        self.bezel = bezel = round(screen_width * BEZEL)
        self.size = size = (screen_width + 2 * bezel, screen_height + 2 * bezel)
        radius = screen_width * CORNER
        rim = max(1, round(screen_width * RIM))

        body = Image.new("RGBA", size, RIM_COLOR)
        body.putalpha(rounded_mask(size, (0, 0, *size), radius + bezel))
        inner = Image.new("RGBA", size, BEZEL_COLOR)
        inner.putalpha(rounded_mask(size, (rim, rim, size[0] - rim, size[1] - rim), radius + bezel - rim))
        self.body = Image.alpha_composite(body, inner)

        self.screen_mask = rounded_mask(size, (bezel, bezel, bezel + screen_width, bezel + screen_height), radius)
        island_width, island_height = screen_width * ISLAND_WIDTH, screen_width * ISLAND_HEIGHT
        left, top = bezel + (screen_width - island_width) / 2, bezel + screen_width * ISLAND_TOP
        island = Image.new("RGBA", size, (0, 0, 0, 255))
        island.putalpha(rounded_mask(size, (left, top, left + island_width, top + island_height), island_height / 2))
        self.island = island

    def __call__(self, screen):
        screen_layer = Image.new("RGBA", self.size)
        screen_layer.paste(screen.convert("RGB"), (self.bezel, self.bezel))
        screen_layer.putalpha(self.screen_mask)
        framed = Image.alpha_composite(self.body, screen_layer)
        return Image.alpha_composite(framed, self.island)


def with_shadow(image, blur=18, offset=14, opacity=0.34, pad=36):
    width, height = image.size
    canvas = (width + 2 * pad, height + 2 * pad)
    alpha = Image.new("L", canvas, 0)
    alpha.paste(image.getchannel("A"), (pad, pad + offset))
    alpha = alpha.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: round(v * opacity))
    shadowed = Image.new("RGBA", canvas, (*SHADOW_COLOR, 0))
    shadowed.putalpha(alpha)
    shadowed.alpha_composite(image, (pad, pad))
    return shadowed


def save_png(image, path):
    image.save(path, optimize=True)
    if shutil.which("pngquant"):
        subprocess.run(["pngquant", "--quality", "80-98", "--speed", "1", "--strip", "--force",
                        "--output", str(path), str(path)], check=True)


def fit_width(image, width):
    return image.resize((width, round(image.height * width / image.width)), Image.LANCZOS)


# MARK: - Timeline

class Timeline:
    """One appearance's tour: its steps, screenshots and recording."""

    def __init__(self, render, appearance, offset=0.0):
        self.appearance = appearance
        self.folder = render / appearance
        self.steps = json.loads((self.folder / "timeline.json").read_text())
        self.video = render / f"{appearance}.mp4"
        start_file = render / f"{appearance}.video-start"
        self.video_start = float(start_file.read_text()) - offset if start_file.exists() else None
        first = next(step["file"] for step in self.steps if "file" in step)
        with Image.open(self.folder / first) as image:
            self.points_high = image.height / POINT_SCALE

    def shot(self, name):
        for step in self.steps:
            if step["step"] == f"shot:{name}":
                return Image.open(self.folder / step["file"]).convert("RGB")
        sys.exit(f"No shot named {name} in {self.folder}")

    def index(self, name, after=-1):
        for i, step in enumerate(self.steps):
            if i > after and step["step"] == name:
                return i
        sys.exit(f"No step {name!r} after step {after} in {self.folder / 'timeline.json'}")

    def time(self, spec, after=-1):
        """Recording time of "step@edge±seconds", where edge is start, end or
        touch; the step is the first with that name after step `after`.
        Returns (seconds, step index)."""
        match = re.fullmatch(r"(.+?)@(start|end|touch)([+-][\d.]+)?", spec)
        if not match:
            sys.exit(f"Bad time {spec!r}: expected step@start|end|touch[±seconds]")
        name, edge, shift = match.group(1), match.group(2), float(match.group(3) or 0)
        i = self.index(name, after)
        step = self.steps[i]
        if edge == "end" and "end" not in step:
            sys.exit(f"Step {name!r} didn't finish in {self.folder / 'timeline.json'}")
        moment = step["touch"]["time"] if edge == "touch" else step[edge]
        return moment - self.video_start + shift, i

    def touches(self, start, end):
        """Touches between two recording times: (time, x, y, to_x, to_y)."""
        found = []
        for step in self.steps:
            touch = step.get("touch")
            if not touch or "time" not in touch:
                continue
            moment = touch["time"] - self.video_start
            if start - 1 <= moment <= end:
                finished = step.get("end", touch["time"] + 1) - self.video_start
                found.append((moment, touch["x"], touch["y"], touch.get("toX"), touch.get("toY"), finished))
        return found


# MARK: - Touch dots

def dot(draw, x, y, radius, strength):
    """A fingertip: a soft white disc with a ring, visible on light and dark."""
    if strength <= 0:
        return
    box = [x - radius, y - radius, x + radius, y + radius]
    draw.ellipse([x - radius - 1.5, y - radius - 1.5, x + radius + 1.5, y + radius + 1.5],
                 outline=(8, 24, 14, round(70 * strength)), width=2)
    draw.ellipse(box, fill=(255, 255, 255, round(120 * strength)),
                 outline=(255, 255, 255, round(235 * strength)), width=2)


def reaction_time(frames, times, touch_time, until):
    """When the screen first changes after a tap was sent, or None."""
    start = int(np.searchsorted(times, touch_time))
    stop = min(int(np.searchsorted(times, until + 0.6)), len(frames))
    if start >= stop - 1:
        return None
    base = frames[start].astype(np.int16)
    for i in range(start + 1, stop):
        changed = np.abs(frames[i].astype(np.int16) - base).max(axis=2) > 24
        if changed.mean() > 0.0015:
            return times[i]
    return None


def draw_touches(frames, times, touches, points_high):
    """Draws a fingertip on the frames (RGB arrays, changed in place) where and
    when each tap or glide lands. `points_high` is the screen's height in points."""
    height, width = frames[0].shape[:2]
    radius = width * 0.06
    tracks = []
    for moment, x, y, to_x, to_y, end in touches:
        seen = reaction_time(frames, times, moment, end)
        down = seen - 0.05 if seen is not None else moment + TOUCH_MISSING_DELAY
        if to_y is None:
            tracks.append(([(down - 0.06, x, y), (down + 0.22, x, y)], 0.28))
        else:
            # RenderCheckUITests' glide: a 0.05 s press, a drag at 500 pt/s, a 0.25 s hold
            travel = abs(to_y - y) * points_high / 500
            tracks.append(([(down - 0.06, x, y), (down + 0.05, x, y),
                            (down + 0.05 + travel, to_x, to_y), (down + 0.3 + travel, to_x, to_y)], 0.2))

    for track, fade_out in tracks:
        first, lift = track[0][0], track[-1][0]
        for i in np.nonzero((times >= first) & (times <= lift + fade_out))[0]:
            t = times[i]
            if t <= lift:
                for (t0, x0, y0), (t1, x1, y1) in zip(track, track[1:]):
                    if t <= t1:
                        k = (t - t0) / (t1 - t0) if t1 > t0 else 1
                        k = k * k * (3 - 2 * k)
                        px, py = x0 + (x1 - x0) * k, y0 + (y1 - y0) * k
                        break
                strength, scale = 1.0, 0.75 + 0.25 * min(1, (t - first) / 0.08)
            else:
                k = (t - lift) / fade_out
                px, py = track[-1][1], track[-1][2]
                strength, scale = 1 - k, 1 + 0.35 * k
            layer = Image.fromarray(frames[i]).convert("RGBA")
            overlay = Image.new("RGBA", layer.size, (0, 0, 0, 0))
            dot(ImageDraw.Draw(overlay), px * width, py * height, radius * scale, strength)
            frames[i] = np.asarray(Image.alpha_composite(layer, overlay).convert("RGB"))


# MARK: - Clips

def shorten_pauses(frames, fps, max_still, end_still):
    """Drops frames from runs where nothing moves, keeping `max_still` seconds
    of each (and `end_still` of the last)."""
    keep_run, keep_end = round(max_still * fps), round(end_still * fps)
    kept, run = [], 0
    previous = None
    for frame in frames:
        small = frame[::4, ::4].astype(np.int16)
        still = previous is not None and np.abs(small - previous).mean() < 0.6
        previous = small
        run = run + 1 if still else 0
        if run <= keep_run:
            kept.append(frame)
    # the last run: stretch or trim to end_still
    tail = 0
    while tail < len(kept) - 1 and np.abs(kept[-1 - tail].astype(np.int16)[::4, ::4]
                                          - kept[-2 - tail].astype(np.int16)[::4, ::4]).mean() < 0.6:
        tail += 1
    kept = kept[:len(kept) - tail] + [kept[-1]] * keep_end
    return kept


def crossfade_to_start(frames, fps, seconds):
    count = round(seconds * fps)
    first, last = frames[0].astype(np.float32), frames[-1].astype(np.float32)
    for i in range(1, count + 1):
        k = i / (count + 1)
        k = k * k * (3 - 2 * k)
        frames.append((last * (1 - k) + first * k).round().astype(np.uint8))
    return frames


def build_clips(timelines, clips, frame):
    by_appearance = {}
    for clip in clips:
        by_appearance.setdefault(clip.appearance, []).append(clip)

    for appearance, wanted in by_appearance.items():
        timeline = timelines[appearance]
        if timeline.video_start is None or not timeline.video.exists():
            print(f"!! No {appearance} recording; skipping {', '.join(c.name for c in wanted)}")
            continue
        video_width, video_height = video_size(timeline.video)
        width, height = GIF_WIDTH, round(video_height * GIF_WIDTH / video_width / 2) * 2
        ranges = []
        for clip in wanted:
            start, i = timeline.time(clip.start)
            end, _ = timeline.time(clip.end, after=i - 1)
            ranges.append((clip, start, end))
        print(f"== Decoding the {appearance} recording for {', '.join(c.name for c in wanted)}")
        collected = {clip.name: ([], []) for clip in wanted}
        for k, image in enumerate(decode(timeline.video, width, height)):
            moment = k / DECODE_FPS
            for clip, start, end in ranges:
                step = DECODE_FPS // clip.fps
                if start <= moment <= end and k % step == 0:
                    collected[clip.name][0].append(image.copy())
                    collected[clip.name][1].append(moment)

        for clip, start, end in ranges:
            images, times = collected[clip.name]
            if not images:
                print(f"!! {clip.name}: nothing between {start:.1f}s and {end:.1f}s of the recording")
                continue
            times = np.array(times)
            draw_touches(images, times, timeline.touches(start, end), timeline.points_high)
            images = shorten_pauses(images, clip.fps, clip.max_still, clip.end_still)
            images = crossfade_to_start(images, clip.fps, clip.fade)
            framed = [np.asarray(frame(Image.fromarray(image))) for image in images]
            path = OUT / f"{clip.name}.gif"
            encode_gif(framed, clip.fps, path)
            print(f"   {path.name}: {len(framed)} frames, "
                  f"{len(framed) / clip.fps:.1f}s, {path.stat().st_size / 1e6:.2f} MB")


def build_theme_gif(timelines, shots, frame, fps=15, hold=1.3, reveal=0.75):
    """Light and Dark of each shot, the other revealed in a growing circle."""
    frames = []
    size = None
    for name in shots:
        light = fit_width(timelines["light"].shot(name), GIF_WIDTH)
        dark = fit_width(timelines["dark"].shot(name), GIF_WIDTH)
        size = light.size
        width, height = size
        # the circle grows from the top right, where Control Center's switch is
        center = (width * 0.86, height * 0.04)
        far = math.hypot(width, height)
        for a, b in ((light, dark), (dark, light)):
            frames += [a] * round(hold * fps)
            steps = round(reveal * fps)
            for i in range(1, steps + 1):
                k = i / steps
                k = k * k * (3 - 2 * k)
                mask = rounded_mask(size, (center[0] - far * k, center[1] - far * k,
                                           center[0] + far * k, center[1] + far * k), far * k, supersample=2)
                frames.append(Image.composite(b, a, mask))
    framed = [np.asarray(frame(image)) for image in frames]
    path = OUT / "theme.gif"
    encode_gif(framed, fps, path)
    print(f"   {path.name}: {len(framed)} frames, {path.stat().st_size / 1e6:.2f} MB")


# MARK: - Stills and banner

def still_image(timeline, still):
    if still.shot:
        return timeline.shot(still.shot)
    moment, _ = timeline.time(still.at)
    width, height = video_size(timeline.video)
    for image in decode(timeline.video, width, height, start=max(0, moment), count=1):
        return Image.fromarray(image.copy())
    sys.exit(f"No frame at {still.at} in {timeline.video}")


def build_stills(timelines, stills):
    images = {}
    folder = OUT / "screens"
    folder.mkdir(parents=True, exist_ok=True)
    frames = {}
    for still in stills:
        for appearance in still.appearances:
            timeline = timelines.get(appearance)
            if not timeline:
                continue
            screen = fit_width(still_image(timeline, still), STILL_WIDTH)
            frame = frames.setdefault(screen.size, DeviceFrame(*screen.size))
            framed = frame(screen)
            images[(still.name, appearance)] = framed
            suffix = "" if appearance == "dark" else f"-{appearance}"
            path = folder / f"{still.name}{suffix}.png"
            save_png(with_shadow(framed), path)
    print(f"   {folder.name}/: {len(images)} screenshots")
    return images


def build_banner(images, shots, size=(1760, 880), corner=36):
    """The phones fanned out over the app's forest, for the top of the README."""
    width, height = size
    forest = Image.open(FOREST).convert("RGB")
    scale = max(width / forest.width, height / forest.height)
    forest = forest.resize((round(forest.width * scale), round(forest.height * scale)), Image.LANCZOS)
    top = (forest.height - height) // 2
    forest = forest.crop((0, top, width, top + height)).filter(ImageFilter.GaussianBlur(10))
    background = np.asarray(forest).astype(np.float32)
    # darken towards the edges, and a green glow behind the middle phone
    ys, xs = np.mgrid[0:height, 0:width]
    glow = np.exp(-(((xs - width / 2) / (width * 0.32)) ** 2 + ((ys - height * 0.62) / (height * 0.55)) ** 2))
    tint = np.array([31, 122, 70], np.float32)
    background = background * (0.55 + 0.25 * glow[..., None]) + tint * (0.28 * glow[..., None])
    banner = Image.fromarray(background.clip(0, 255).astype(np.uint8)).convert("RGBA")

    # middle phone largest, the others smaller and further down, drawn outside in
    middle = len(shots) // 2
    placements = []
    for i, name in enumerate(shots):
        distance = abs(i - middle)
        scale = [1.0, 0.86, 0.74][min(distance, 2)]
        phone = images.get((name, "dark"))
        if phone is None:
            continue
        phone = fit_width(phone, round(330 * scale))
        x = width / 2 + (i - middle) * 300 - phone.width / 2
        y = 88 + distance * 70
        placements.append((distance, phone, round(x), y))
    for distance, phone, x, y in sorted(placements, key=lambda p: -p[0]):
        shadowed = with_shadow(phone, blur=22, offset=18, opacity=0.55, pad=48)
        if distance:
            # the further phones sit a little back in the forest
            dim = Image.new("RGBA", shadowed.size, (7, 20, 13, 0))
            dim.putalpha(shadowed.getchannel("A").point(lambda v: round(v * 0.18 * distance)))
            shadowed = Image.alpha_composite(shadowed, dim)
        banner.alpha_composite(shadowed, (x - 48, y - 48))

    banner.putalpha(rounded_mask(size, (0, 0, width, height), corner))
    path = OUT / "banner.png"
    save_png(banner, path)
    print(f"   {path.name}: {path.stat().st_size / 1e6:.2f} MB")


def build_icon(size=256):
    """The app icon with the rounded corners iOS gives it."""
    icon = Image.open(ICON).convert("RGBA").resize((size, size), Image.LANCZOS)
    icon.putalpha(rounded_mask((size, size), (0, 0, size, size), size * 0.2237))
    path = OUT / "icon.png"
    save_png(icon, path)
    print(f"   {path.name}: {path.stat().st_size / 1e3:.0f} kB")


def main():
    global OUT
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("render", type=Path, help="the downloaded render artifact")
    parser.add_argument("--only", nargs="*", help="build only these: icon, stills, banner, theme, or clip names")
    parser.add_argument("--offset", type=float, default=0.0,
                        help="seconds the recordings start before their stamped start time")
    parser.add_argument("--out", type=Path, default=OUT, help=f"where to write (default {OUT.relative_to(ROOT)})")
    args = parser.parse_args()
    OUT = args.out.resolve()

    timelines = {appearance: Timeline(args.render, appearance, args.offset)
                 for appearance in ("light", "dark") if (args.render / appearance / "timeline.json").exists()}
    if not timelines:
        sys.exit(f"No light/timeline.json or dark/timeline.json in {args.render}")
    only = set(args.only or [])
    wanted = lambda name: not only or name in only
    OUT.mkdir(parents=True, exist_ok=True)

    if wanted("icon"):
        print("== Icon")
        build_icon()
    if wanted("stills") or wanted("banner"):
        print("== Screenshots")
        images = build_stills(timelines, STILLS)
        if wanted("banner"):
            build_banner(images, BANNER_SHOTS)
    if wanted("theme") and {"light", "dark"} <= timelines.keys():
        print("== Light and Dark")
        width, height = fit_width(timelines["dark"].shot(THEME_SHOTS[0]), GIF_WIDTH).size
        build_theme_gif(timelines, THEME_SHOTS, DeviceFrame(width, height))
    clips = [clip for clip in CLIPS if wanted(clip.name) and clip.appearance in timelines]
    if clips:
        print("== GIFs")
        sample = timelines[clips[0].appearance].shot("home")
        width, height = GIF_WIDTH, round(sample.height * GIF_WIDTH / sample.width / 2) * 2
        build_clips(timelines, clips, DeviceFrame(width, height))


if __name__ == "__main__":
    main()
