"""Serial monitor filter that colors the board's log. platformio.ini turns it
on through monitor_filters; the rules live in scripts/log_colors.py, which
scripts/viewer.py also uses. Set NO_COLOR=1 to turn the colors off."""

import importlib.util
from pathlib import Path

from platformio.public import DeviceMonitorFilterBase

_spec = importlib.util.spec_from_file_location(
    "aware_log_colors", Path(__file__).resolve().parent.parent / "scripts" / "log_colors.py")
log_colors = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(log_colors)


class AwareLogColors(DeviceMonitorFilterBase):
    NAME = "aware_log_colors"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.painter = log_colors.LogPainter() if log_colors.enabled() else None

    def rx(self, text):
        if self.painter:
            return self.painter.feed(text)
        return log_colors.COLOR_CODE.sub("", text)  # NO_COLOR: the board's own colors too
