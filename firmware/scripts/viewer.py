"""Shows each photo the board sends, with the server's boxes and the decision.

Use it instead of the serial monitor (only one program can use the port). It
prints the board's log, and lines typed here go to the board. Run from the
repository root:

    firmware/.venv/bin/python firmware/scripts/viewer.py [port]

For the Wokwi simulator, start it first and use rfc2217://localhost:4000 as
the port. The board sends a photo after every scan and every `snap`.
"""

import base64
import io
import queue
import re
import sys
import threading
import tkinter as tk

import serial
from PIL import Image, ImageDraw, ImageFont, ImageTk
from serial.tools import list_ports

DETECTED = re.compile(r"\[scan\] detected (\S+) ([\d.]+) box (-?\d+),(-?\d+),(-?\d+),(-?\d+)")
BEGIN = re.compile(r"-----BEGIN JPEG (\d+)-----")
FONT = ImageFont.load_default(size=16)


def find_port():
    ports = [p.device for p in list_ports.comports() if "usb" in p.device.lower()]
    if len(ports) != 1:
        sys.exit(f"Found {len(ports)} USB serial ports {ports}. Name one: viewer.py /dev/cu.usb...")
    return ports[0]


def read_board(link, photos):
    """Prints the log; queues (jpeg, boxes, decision) for each photo."""
    boxes, decision, jpeg = [], "", None
    while True:
        line = link.readline().decode("ascii", "replace").strip()
        if jpeg is not None:
            if line == "-----END JPEG-----":
                photos.put(("".join(jpeg), boxes, decision))
                jpeg = None
            elif line:
                jpeg.append(line)
            continue
        if not line:
            continue
        if BEGIN.match(line):
            jpeg = []
            continue
        print(line)
        if line == "[scan] start":
            boxes, decision = [], ""
        elif line.startswith("[camera] photo"):
            boxes, decision = [], "snap: photo only, not sent to the server"
        elif match := DETECTED.match(line):
            boxes.append((match[1], float(match[2]), *map(int, match.groups()[2:])))
        elif line.startswith("[route] "):
            decision = line.removeprefix("[route] ")


def forward_typing(link):
    for line in sys.stdin:
        link.write(line.encode())


def label(draw, xy, text, color):
    left, top, right, bottom = draw.textbbox(xy, text, font=FONT)
    draw.rectangle((left - 4, top - 3, right + 4, bottom + 3), fill=color)
    draw.text(xy, text, fill="black", font=FONT)


def render(jpeg, boxes, decision):
    image = Image.open(io.BytesIO(base64.b64decode(jpeg))).convert("RGB")
    draw = ImageDraw.Draw(image)
    for name, conf, x1, y1, x2, y2 in boxes:
        draw.rectangle((x1, y1, x2, y2), outline="yellow", width=3)
        label(draw, (x1 + 6, y1 + 5), f"{name} {conf:.2f}", "yellow")
    if decision:
        label(draw, (10, image.height - 28), decision, "white")
    return image


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else find_port()
    link = serial.serial_for_url(port, baudrate=921600, timeout=1, do_not_open=True)
    link.dtr = link.rts = False  # so opening the port doesn't reset the board
    try:
        link.open()
    except serial.SerialException as e:
        sys.exit(f"Can't open {port}: {e}\nIs the serial monitor still open? Close it with Ctrl+C.")

    photos = queue.Queue()
    threading.Thread(target=read_board, args=(link, photos), daemon=True).start()
    threading.Thread(target=forward_typing, args=(link,), daemon=True).start()

    root = tk.Tk()
    root.title("AWARE bin camera")
    view = tk.Label(root, text="Waiting for a photo. Press BOOT, or type scan or snap in the terminal.",
                    padx=40, pady=40)
    view.pack()

    def show_photos():
        while not photos.empty():
            try:
                image = ImageTk.PhotoImage(render(*photos.get()))
            except Exception as e:  # text lost on the cable
                print(f"[viewer] photo arrived damaged ({e}); try again")
                continue
            view.configure(image=image, text="", padx=0, pady=0)
            view.image = image  # Tk shows nothing if the image is garbage-collected
        root.after(100, show_photos)

    show_photos()
    link.write(b"snap\n")
    root.mainloop()


if __name__ == "__main__":
    main()
