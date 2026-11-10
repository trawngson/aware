"""Colors for the board's serial log, shared by the serial monitor
(monitor/filter_aware_log_colors.py) and scripts/viewer.py.

A line's color comes from how it starts: its [tag], and for a few tags the
first words, so failures show in red and warnings in yellow. RULES is the
whole rule set. Set NO_COLOR=1 to turn the colors off.
"""

import os
import re

RED, YELLOW, GREEN, BOLD_GREEN, BLUE, MAGENTA, CYAN, GREY, BOLD = (
    "31", "33", "32", "1;32", "34", "35", "36", "90", "1")

# (start of the line, color). The first match wins, so a specific start comes
# before the general one it begins with: "[link] could not" before "[link] ".
# No start begins with a lowercase letter: the board echoes typed commands,
# and those must show as they are typed, not wait for a color.
RULES = (
    # Failures: the servo stays home, the network fails, or the chip crashes
    ("[hold] ", RED),
    ("[link] could not", RED),
    ("[link] bad server", RED),
    ("[wifi] could not", RED),
    ("[camera] start failed", RED),
    ("[servo] could not", RED),
    ("[llm] could not", RED),
    ("[llm] the sign-in failed", RED),
    ("[llm] ChatGPT ended", RED),
    ("[llm] no Wi-Fi", RED),
    ("Bad server address", RED),
    ("Camera: NOT ready", RED),
    ("Guru Meditation", RED),
    ("Backtrace:", RED),
    ("  #", RED),  # a crash address, turned into code by the exception decoder
    ("Rebooting...", RED),
    ("E (", RED),  # ESP-IDF error
    ("[T][E]", RED),  # Arduino core error; [T] stands for its timestamp
    # Warnings
    ("[wifi] disconnected", YELLOW),
    ("[wifi] no network", YELLOW),
    ("[link] the ", YELLOW),  # the server closed the connection, or it was dead
    ("[camera] no PSRAM", YELLOW),
    ("[camera] simulator: no photos", YELLOW),
    ("[viewer] ", YELLOW),
    ("[busy] ", YELLOW),  # a command waits for the camera or servo, or was skipped
    ("[llm] nobody entered", YELLOW),
    ("[llm] sign-in stopped", YELLOW),
    ("Usage:", YELLOW),
    ("Unknown command", YELLOW),
    ("W (", YELLOW),
    ("[T][W]", YELLOW),
    # The steps of a scan
    ("[watch] ", CYAN),
    ("[feed] ", CYAN),
    ("[camera] ", CYAN),
    ("[scan] ", GREEN),
    ("[route] ", BOLD_GREEN),
    ("[servo] ", MAGENTA),
    ("[wifi] ", BLUE),
    ("[link] ", BLUE),
    ("[llm] To sign", BOLD),  # the sign-in code to type
    ("[llm] ", BLUE),
    ("[time] ", GREY),
    # Background
    ("I (", GREY),
    ("D (", GREY),
    ("V (", GREY),
    ("[T]", GREY),
    ("-----BEGIN ", GREY),  # a photo (JPEG) or a live view frame (LIVE)
    ("AWARE bin MVP", BOLD),
    ("Ready.", BOLD),
)

HOLD = object()  # "need more of the line to choose"
RESET = "\x1b[0m"
TIMESTAMP = re.compile(r"\[ *\d+\]")  # Arduino core: "[  1234][E][file.cpp:12] ..."
PART_TIMESTAMP = re.compile(r"\[ *\d*")
BASE64 = re.compile(r"[A-Za-z0-9+/=]*")
# The board's prompt sits on the last line. To print above it, the board
# goes back to the line's start and clears it; what follows is a new line.
LINE_RESTART = "\r\x1b[2K"
TOKENS = re.compile(r"(\n|\r\x1b\[2K)")
COLOR_CODE = re.compile(r"\x1b\[[0-9;]*m")  # the board's own colors (prompt, status)


def enabled():
    return not os.environ.get("NO_COLOR")


def color_for(start, complete=True):
    """The color for a line that begins with `start` ("" for none). With
    complete=False the line may go on, and this returns HOLD while the rest
    could still change the answer."""
    if match := TIMESTAMP.match(start):
        start = "[T]" + start[match.end():]
    elif not complete and PART_TIMESTAMP.fullmatch(start):
        return HOLD
    for prefix, color in RULES:
        if start.startswith(prefix):
            return color
        if not complete and prefix.startswith(start):
            return HOLD
    return ""


def paint(line):
    """Colors one whole line."""
    color = color_for(line)
    return f"\x1b[{color}m{line}{RESET}" if color else line


class LogPainter:
    """Colors the log as it streams in, in whatever pieces the serial port
    delivers. A line shows once its start picks a color; until then the few
    characters so far wait. The board prints each line in one go, so they
    normally wait for no time at all. A photo's text is grey throughout."""

    def __init__(self):
        self.line = ""  # the current line so far
        self.color = None  # None until the line's start picks one
        self.in_photo = False
        self.carry = ""  # the start of a LINE_RESTART that a piece cut off

    def feed(self, text):
        text, self.carry = self.carry + text, ""
        for n in range(len(LINE_RESTART) - 1, 0, -1):
            if text.endswith(LINE_RESTART[:n]):
                text, self.carry = text[:-n], LINE_RESTART[:n]
                break
        out = []
        for token in TOKENS.split(text):
            if token == "\n":
                if self.color is None and self.line:
                    self.start_line(out, complete=True)
                out.append(RESET + "\n" if self.color else "\n")
                self.end_line()
            elif token == LINE_RESTART:
                # The board cleared the prompt line; a log line follows
                out.append(RESET + token if self.color else token)
                self.line, self.color = "", None
            elif token:
                self.line += token
                if self.color is None:
                    self.start_line(out, complete=False)
                else:
                    out.append(token)
        return "".join(out)

    def start_line(self, out, complete):
        """Shows the line so far once its start picks a color."""
        color = GREY if self.in_photo else color_for(self.line, complete)
        if color is HOLD:
            return  # wait for more of the line
        self.color = color
        out.append(f"\x1b[{color}m{self.line}" if color else self.line)

    def end_line(self):
        line = self.line.rstrip("\r")
        if self.in_photo:
            # The END line, or any line that isn't base64 (the photo was cut
            # off, e.g. by a reset), ends the photo
            self.in_photo = bool(BASE64.fullmatch(line))
        else:
            self.in_photo = line.startswith("-----BEGIN ")
        self.line, self.color = "", None
