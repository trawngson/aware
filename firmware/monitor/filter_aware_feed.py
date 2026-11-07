"""Serial monitor filter for `feed`: opens the live camera window.

Type `feed` in the monitor. The board answers "[feed] opening the live view
on the Mac", and this filter starts scripts/viewer.py --pipe: a window with
the live view, the last scan and the scan's stage. The filter hands the
window the board's output, sends the board the heartbeat that keeps the
stream on, and keeps photos out of the terminal: the board sends a photo's
text (a frame of the stream, or a scan's or snap's photo) between the bytes
STX and ETX, and everything between them stays out, wherever it comes, so the
prompt line is left alone. Close the window, type `feed off`, or quit the
monitor to stop.

platformio.ini turns it on through monitor_filters, before aware_log_colors.
"""

import atexit
import re
import subprocess
import threading
from pathlib import Path

from platformio.public import DeviceMonitorFilterBase

FIRMWARE = Path(__file__).resolve().parent.parent
VIEWER = FIRMWARE / "scripts" / "viewer.py"
PYTHON = FIRMWARE / ".venv" / "bin" / "python"  # has pyserial and Pillow (see the README's Viewer section)
HEARTBEAT = b"\x1e"  # kViewerHeartbeat in include/console.h: "keep the live view on"
STX, ETX = "\x02", "\x03"  # a photo's text comes between these (sendPhoto in src/main.cpp)
LINE_RESTART = "\r\x1b[2K"  # the board clears its prompt line to print above it
TOKENS = re.compile(r"(\n|\r\x1b\[2K)")
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


class AwareFeed(DeviceMonitorFilterBase):
    NAME = "aware_feed"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewer = None  # the window's process
        self.photo = None  # the start of the photo coming in, while one is
        self.visible = ""  # the current line on screen
        self.notes = []  # this filter's own messages, for the next chance to print
        self.hinted = False  # said once where hidden photos can be seen
        atexit.register(self.close_viewer)

    # ---- The window ---------------------------------------------------------

    def viewer_open(self):
        return self.viewer is not None and self.viewer.poll() is None

    def open_viewer(self):
        if self.viewer_open():
            self.notes.append("[feed] the live view is already open")
            return
        if not PYTHON.exists():
            self.notes.append("[feed] the window needs its Python packages first: python3 -m venv firmware/.venv "
                              "&& firmware/.venv/bin/pip install pyserial pillow")
            return
        self.viewer = subprocess.Popen([str(PYTHON), str(VIEWER), "--pipe"], stdin=subprocess.PIPE,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        threading.Thread(target=self.keep_live, args=(self.viewer,), daemon=True).start()

    def close_viewer(self):
        if self.viewer_open():
            self.viewer.terminate()

    def keep_live(self, viewer):
        """Sends the heartbeat about once a second while the window is open;
        the board stops streaming a few seconds after it closes."""
        while viewer.poll() is None:
            terminal = self.get_running_terminal()
            try:
                terminal.serial.write(HEARTBEAT)
            except Exception:  # no terminal yet, or the board was unplugged
                pass
            try:
                viewer.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
        if viewer.returncode not in (0, -15):  # not closed by hand or by "feed off"
            self.notes.append(f"[feed] the window stopped (exit code {viewer.returncode}). To see why, quit the "
                              "monitor and run firmware/.venv/bin/python firmware/scripts/viewer.py")

    def send(self, text):
        if not self.viewer_open():
            return
        try:
            self.viewer.stdin.write(text.encode("utf-8", "replace"))
            self.viewer.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            pass  # the window just closed

    # ---- The terminal -------------------------------------------------------

    def photo_done(self, header):
        if header.startswith("-----BEGIN JPEG") and not self.hinted and not self.viewer_open():
            self.hinted = True
            self.notes.append("[feed] photos don't print here; type feed to see them and the live camera")

    def track(self, text):
        """Follows the visible text: whole lines for the [feed] messages, and
        the current line, to put back after a message of this filter's own."""
        for token in TOKENS.split(text):
            if token == "\n":
                line = ANSI.sub("", self.visible).rstrip("\r").split("\r")[-1].strip()
                self.visible = ""
                self.on_line(line)
            elif token == LINE_RESTART:
                self.visible = ""
            elif token:
                self.visible += token

    def on_line(self, line):
        if line.startswith("[feed] opening the live view"):
            self.open_viewer()
        elif line.startswith("[feed] closing the live view"):
            self.close_viewer()

    def rx(self, text):
        self.send(text)
        out = []
        while text:
            if self.photo is None:
                start = text.find(STX)
                shown = text if start < 0 else text[:start]
                out.append(shown)
                self.track(shown)
                if start < 0:
                    break
                self.photo, text = "", text[start + 1:]
            else:
                end = text.find(ETX)
                if end < 0:
                    self.photo = (self.photo + text)[:40]  # the header is enough
                    break
                self.photo_done((self.photo + text[:end])[:40])
                self.photo, text = None, text[end + 1:]
        if self.notes and self.photo is None:
            # Above the prompt line, which then comes back as it was
            notes, self.notes = self.notes, []
            out.append(LINE_RESTART + "\r\n".join(notes) + "\r\n" + self.visible)
        return "".join(out)
