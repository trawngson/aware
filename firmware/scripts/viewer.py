"""Shows the board's camera live, with the latest scan's boxes and decision.

Use it instead of the serial monitor (only one program can use the port). It
prints the board's log, and lines typed here go to the board. Run from the
repository root:

    firmware/.venv/bin/python firmware/scripts/viewer.py [port]

While the window is open the board streams its camera over the USB cable,
about 10 frames a second, and pauses the stream during a scan. The latest
scan's photo, with the server's boxes and the decision, sits beside the live
view, and the bar below follows each scan like the board's LED: blue while
scanning, green when sorted, red when held.

For the Wokwi simulator, start it first and use rfc2217://localhost:4000 as
the port. It has no live camera, so only scan photos show. Close the window,
press Ctrl+C in the terminal, or unplug the board to quit.

With --pipe it opens only the window, and reads the board's output from its
standard input instead of the port: the PlatformIO monitor's aware_feed
filter starts it that way when you type `feed` there.
"""

import base64
import collections
import io
import os
import queue
import re
import signal
import sys
import threading
import time
import tkinter as tk

import serial
from PIL import Image, ImageDraw, ImageFont, ImageTk
from serial.tools import list_ports

import log_colors

BAUD = 2_000_000  # SERIAL_BAUD in include/config.h
HEARTBEAT = b"\x1e"  # kViewerHeartbeat in include/console.h: "keep the live view on"
RESULT_SECONDS = 3  # LED_RESULT_MS in include/config.h: how long green or red stays
LIVE_SIZE = (640, 480)
SCAN_SIZE = (480, 360)

PIPE = "--pipe" in sys.argv[1:]  # opened by the monitor's aware_feed filter: window only
# The log in the monitor's colors, unless printing to a file
COLOR = sys.stdout.isatty() and log_colors.enabled()
paint = log_colors.paint if COLOR else str
DETECTED = re.compile(r"\[scan\] detected (\S+) ([\d.]+) box (-?\d+),(-?\d+),(-?\d+),(-?\d+)")
SAW = re.compile(r"\[scan\] (\S+) saw (.+)")  # LLM mode: the model's items, no boxes
BEGIN = re.compile(r"-----BEGIN (JPEG|LIVE) (\d+)-----")
PHOTO_TEXT = re.compile(r"[A-Za-z0-9+/=]+")  # base64
STX, ETX = b"\x02", b"\x03"  # a photo's text comes between these (sendPhoto in include/scan.h)
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
CLEAR_LINE = "\x1b[2K"
FONT = ImageFont.load_default(size=16)

BACKGROUND, TEXT, EMPTY = "#1e1e1e", "#e6e6e6", "#111111"
STAGE_COLORS = {"ready": "#3c3c3c", "scanning": "#1f5fbf", "sorted": "#1e8c46", "held": "#b8322f"}


def find_port():
    ports = [p.device for p in list_ports.comports() if "usb" in p.device.lower()]
    if len(ports) != 1:
        sys.exit(f"Found {len(ports)} USB serial ports {ports}. Name one: viewer.py /dev/cu.usb...")
    return ports[0]


def port_chunks(link, port):
    """Yields what the board sends, and ends when the board is unplugged. The
    Mac's driver for the board's CH343 USB chip sometimes says data is
    waiting when none is, and pyserial raises on that; skip it, as long as
    the port is still there. Reading only what is waiting loses no bytes."""
    while True:
        try:
            yield link.read(max(1, link.in_waiting))
        except (serial.SerialException, OSError):
            if not os.path.exists(port):  # unplugged (or, for the simulator, its connection closed)
                return
            time.sleep(0.02)


def pipe_chunks():
    """What the board sends, from the monitor through standard input."""
    while chunk := sys.stdin.buffer.read1(65536):
        yield chunk


def split_output(chunks):
    """Turns the board's output into ("line", bytes) and ("photo", bytes)
    items. A photo's text comes between the bytes STX and ETX (sendPhoto in
    include/scan.h), anywhere in the stream, even in the middle of the prompt
    line; the rest is lines."""
    pending, photo = b"", None
    for chunk in chunks:
        while chunk:
            if photo is None:
                start = chunk.find(STX)
                pending += chunk if start < 0 else chunk[:start]
                while b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    yield "line", line
                if start < 0:
                    break
                photo, chunk = b"", chunk[start + 1:]
            else:
                end = chunk.find(ETX)
                if end < 0:
                    photo += chunk
                    break
                yield "photo", photo + chunk[:end]
                photo, chunk = None, chunk[end + 1:]


def split_line(raw):
    """One line of the board's output: as the terminal shows it, and the
    same without colors for reading. The board's prompt redraws its line
    ("\\r", then clear the line) to print above it, so only what follows
    the last redraw is the line."""
    shown = raw.decode("utf-8", "replace").rstrip("\r")
    shown = shown.rsplit("\r", 1)[-1].removeprefix(CLEAR_LINE)
    return shown, ANSI.sub("", shown).strip()


def show(shown, line):
    if not PIPE:  # the monitor prints the log itself
        print(paint(shown) if COLOR else line)


def note(text):
    if not PIPE:
        print(paint(f"[viewer] {text}"))


def label(draw, xy, text, color):
    left, top, right, bottom = draw.textbbox(xy, text, font=FONT)
    draw.rectangle((left - 4, top - 3, right + 4, bottom + 3), fill=color)
    draw.text(xy, text, fill="black", font=FONT)


def decode(text):
    return Image.open(io.BytesIO(base64.b64decode(text))).convert("RGB")


def render(image, boxes, decision, seen=""):
    draw = ImageDraw.Draw(image)
    for name, conf, x1, y1, x2, y2 in boxes:
        draw.rectangle((x1, y1, x2, y2), outline="yellow", width=3)
        label(draw, (x1 + 6, y1 + 5), f"{name} {conf:.2f}", "yellow")
    if seen:
        label(draw, (10, 10), seen, "yellow")
    if decision:
        label(draw, (10, image.height - 28), decision, "white")
    return image


def stage_for(line):
    """The scan stage a log line starts, as (kind, text), or None."""
    if line == "[scan] start" or (line.startswith("[watch]") and line.endswith("scanning")):
        return "scanning", "Scanning..."
    if line.startswith("[route] "):
        return "sorted", "Sorted: " + line.removeprefix("[route] ")
    if line.startswith("[hold] "):
        return "held", "Held: " + line.removeprefix("[hold] ").removesuffix(" The servo stays home.").rstrip(".")
    if line.startswith("[watch] plate empty"):
        return "ready", "Watching the plate"
    return None


def read_board(chunks, events, quitting, ended):
    """Prints the log and turns the board's output into events for the
    window: ("live", image), ("scan", image, caption) and ("stage", kind, text).
    Closes the window when the output ends: the board was unplugged, or the
    monitor quit."""
    read_items(split_output(chunks), events)
    note(ended)
    quitting.set()


def read_photo(data, boxes, decision, seen, events):
    lines = [l.strip() for l in data.decode("ascii", "replace").split("\n")]
    header = BEGIN.match(lines[0]) if lines else None
    if not header:
        return
    try:
        image = decode("".join(l for l in lines[1:] if PHOTO_TEXT.fullmatch(l)))
    except Exception as e:  # text lost on the cable
        if header[1] == "JPEG":
            note(f"photo arrived damaged ({e}); try again")
        return
    if header[1] == "LIVE":
        events.put(("live", image))
    else:
        events.put(("scan", render(image, boxes, decision, seen), decision))


def read_items(items, events):
    boxes, decision, seen = [], "", ""
    for kind, data in items:
        if kind == "photo":
            read_photo(data, boxes, decision, seen, events)
            continue
        shown, line = split_line(data)
        if not line:
            continue
        show(shown, line)
        if stage := stage_for(line):
            events.put(("stage", *stage))
        if line == "[scan] start":
            boxes, decision, seen = [], "", ""
        elif line.startswith("[camera] photo"):
            boxes, decision, seen = [], "snap: photo only, not sent to the server", ""
        elif match := DETECTED.match(line):
            boxes.append((match[1], float(match[2]), *map(int, match.groups()[2:])))
        elif match := SAW.match(line):
            seen = f"{match[1]}: {match[2]}"
        elif line.startswith("[route] "):
            decision = line.removeprefix("[route] ")


def forward_typing(link):
    for line in sys.stdin:
        try:
            link.write(line.encode())
        except (serial.SerialException, OSError):
            return  # unplugged: read_board closes the window


def keep_live(link, quitting):
    """Asks the board for the live view about once a second; it stops
    streaming a few seconds after the window closes."""
    while not quitting.is_set():
        try:
            link.write(HEARTBEAT)
        except (serial.SerialException, OSError):
            return  # unplugged: read_board closes the window
        quitting.wait(1)


def open_port():
    ports = [a for a in sys.argv[1:] if not a.startswith("--")]
    port = ports[0] if ports else find_port()
    link = serial.serial_for_url(port, baudrate=BAUD, timeout=1, do_not_open=True)
    link.dtr = link.rts = False  # so opening the port doesn't reset the board
    try:
        link.open()
    except serial.SerialException as e:
        sys.exit(f"Can't open {port}: {e}\nIs the serial monitor still open? Close it with Ctrl+C, "
                 "or type feed there instead.")
    return port, link


def main():
    events = queue.Queue()
    quitting = threading.Event()
    link = None
    if PIPE:  # the monitor owns the port; it sends the heartbeat and the typing
        threading.Thread(target=read_board, args=(pipe_chunks(), events, quitting, "the monitor quit"),
                         daemon=True).start()
    else:
        port, link = open_port()
        threading.Thread(target=read_board, args=(port_chunks(link, port), events, quitting,
                                                  "the board was unplugged; closing"), daemon=True).start()
        threading.Thread(target=forward_typing, args=(link,), daemon=True).start()
        threading.Thread(target=keep_live, args=(link, quitting), daemon=True).start()

    root = tk.Tk()
    root.title("AWARE bin camera")
    root.configure(bg=BACKGROUND, padx=12, pady=12)
    blank_live = ImageTk.PhotoImage(Image.new("RGB", LIVE_SIZE, EMPTY))
    blank_scan = ImageTk.PhotoImage(Image.new("RGB", SCAN_SIZE, EMPTY))
    title = ("Helvetica", 14, "bold")

    tk.Label(root, text="Live", font=title, bg=BACKGROUND, fg=TEXT).grid(row=0, column=0, sticky="w")
    live_view = tk.Label(root, image=blank_live, text="Waiting for the live view", compound="center",
                         fg=TEXT, bg=EMPTY, bd=0)
    live_view.grid(row=1, column=0, rowspan=2, sticky="n")

    tk.Label(root, text="Last scan", font=title, bg=BACKGROUND, fg=TEXT).grid(row=0, column=1, sticky="w", padx=(12, 0))
    scan_view = tk.Label(root, image=blank_scan, text="No scan yet", compound="center", fg=TEXT, bg=EMPTY, bd=0)
    scan_view.grid(row=1, column=1, sticky="nw", padx=(12, 0))
    scan_caption = tk.Label(root, text="Press BOOT, drop an item on the plate, or type scan.",
                            wraplength=SCAN_SIZE[0], justify="left", anchor="nw", bg=BACKGROUND, fg=TEXT)
    scan_caption.grid(row=2, column=1, sticky="nw", padx=(12, 0), pady=(8, 0))

    bar = tk.Frame(root, bg=STAGE_COLORS["ready"])
    bar.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(12, 0))
    stage_text = tk.Label(bar, text="Connecting to the board...", font=("Helvetica", 16, "bold"),
                          fg="white", bg=STAGE_COLORS["ready"], padx=12, pady=8, anchor="w")
    stage_text.pack(side="left", fill="x", expand=True)
    rate_text = tk.Label(bar, text="", fg="white", bg=STAGE_COLORS["ready"], padx=12)
    rate_text.pack(side="right")

    stage = {"kind": "ready", "at": 0.0}
    frame_times = collections.deque(maxlen=60)

    def set_stage(kind, text):
        stage.update(kind=kind, at=time.monotonic())
        for widget in (bar, stage_text, rate_text):
            widget.configure(bg=STAGE_COLORS[kind])
        stage_text.configure(text=text)

    # Ctrl+C in the terminal, or closing the window, ends the program. Left to
    # Python, a KeyboardInterrupt would land in a Tk callback, which only
    # prints it; refresh runs every 30 ms and notices within that.
    signal.signal(signal.SIGINT, lambda *_: quitting.set())
    root.protocol("WM_DELETE_WINDOW", quitting.set)

    def refresh():
        if quitting.is_set():
            root.destroy()
            return
        now = time.monotonic()
        latest = None
        while True:
            try:
                event = events.get_nowait()
            except queue.Empty:
                break
            if event[0] == "live":
                latest = event[1]
                frame_times.append(now)
            elif event[0] == "scan":
                image = ImageTk.PhotoImage(event[1].resize(SCAN_SIZE))
                scan_view.configure(image=image, text="")
                scan_view.image = image  # Tk shows nothing if the image is garbage-collected
                scan_caption.configure(text=f"{time.strftime('%H:%M:%S')}  {event[2]}")
            elif event[0] == "stage":
                set_stage(event[1], event[2])
        if latest is not None:  # only the newest frame is worth drawing
            image = ImageTk.PhotoImage(latest.resize(LIVE_SIZE) if latest.size != LIVE_SIZE else latest)
            live_view.configure(image=image, text="")
            live_view.image = image
            if stage_text.cget("text").startswith("Connecting"):
                set_stage("ready", "Watching the plate")
        if stage["kind"] in ("sorted", "held") and now - stage["at"] > RESULT_SECONDS:
            set_stage("ready", "Watching the plate")
        recent = [t for t in frame_times if now - t < 2]
        if recent:
            rate_text.configure(text=f"live, {len(recent) / 2:.0f} frames/s")
        elif frame_times:
            rate_text.configure(text="live view paused" if stage["kind"] == "scanning" else "no frames")
        root.after(30, refresh)

    refresh()
    root.mainloop()
    quitting.set()
    if link is not None:
        try:
            link.close()
        except (serial.SerialException, OSError):
            pass  # already gone


if __name__ == "__main__":
    main()
