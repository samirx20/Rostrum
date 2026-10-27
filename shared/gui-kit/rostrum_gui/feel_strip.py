"""The picture strip (feel.py): a grab every 50 ms for 1 s after an action. It answers "was there a frozen gap with
nothing changing, and did something show by 0.2 s?"

    s = strip(win, lambda: QTest.keyClick(win, Qt.Key_G, Qt.ControlModifier))
    s.times[i], s.frames[i], s.changed[i]   # ms after the action; the picture (half size); differs from the one before
    frozen_gaps(s)                          # [(start_ms, end_ms)]: stretches with no change that ended in a change
    s.first_change_ms                       # the first picture that differs from the one before the action (None: none)
    contact_sheet(s, "strip.png")           # every picture in one sheet, its time on it, changed ones framed

The window runs its own event loop between grabs (pointer.wait, never QTest.qWait). A grab draws the window as it is
at that moment (grabWindow lays out and draws), so a 50 ms step is the most often a picture is taken, not a promise:
the times are what they were. Pictures are compared small (THUMB px wide), so a compare costs next to nothing.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

THUMB = 240               # px wide: what "changed?" compares
KEEP = 0.5                # the frames kept for the sheet, at this scale of the window


@dataclass
class Strip:
    times: list[float] = field(default_factory=list)     # ms after the action
    frames: list = field(default_factory=list)           # QImage, KEEP scale
    changed: list[bool] = field(default_factory=list)    # differs from the picture before (the first: from before the action)

    @property
    def first_change_ms(self):
        return next((t for t, c in zip(self.times, self.changed) if c), None)


def _small(img):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage
    s = img.scaledToWidth(THUMB, Qt.TransformationMode.SmoothTransformation).convertToFormat(QImage.Format.Format_RGB32)
    return bytes(s.constBits())


def strip(win, action=None, ms: int = 1000, every: int = 50) -> Strip:
    """Grab `win` every `every` ms for `ms` after `action()` (real input; None: from now)."""
    from PySide6.QtCore import Qt
    from .pointer import wait
    last = _small(win.grabWindow()) if action is not None else None
    out = Strip()
    t0 = time.perf_counter()
    if action is not None:
        action()
    step = 0
    while True:
        now = (time.perf_counter() - t0) * 1000
        img = win.grabWindow()
        if img.isNull():
            raise RuntimeError("strip: the window gave no picture")
        small = _small(img)
        out.times.append(now)
        out.frames.append(img.scaled(int(img.width() * KEEP), int(img.height() * KEEP),
                                     Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation))
        out.changed.append(last is not None and small != last)
        last = small
        step += 1
        if now >= ms:
            return out
        wait(max(1, step * every - (time.perf_counter() - t0) * 1000))    # on the beat, not drifting by the grab's cost


def frozen_gaps(s: Strip) -> list[tuple[float, float]]:
    """Stretches where nothing changed that were followed by a change, longest first: (start_ms, end_ms). The stillness
    after the last change is the screen at rest, not a gap."""
    gaps, still_from = [], 0.0
    for t, c in zip(s.times, s.changed):
        if c:
            if t > still_from:
                gaps.append((still_from, t))
            still_from = t
    return sorted(gaps, key=lambda g: g[0] - g[1])


def contact_sheet(s: Strip, path, cols: int = 5, width: int = 320) -> str:
    """One picture of the whole strip: tiles `width` px wide, the ms on each, a changed tile framed in orange."""
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
    if not s.frames:
        raise RuntimeError("contact_sheet: the strip has no pictures")
    tw = width
    th = round(s.frames[0].height() * tw / s.frames[0].width())
    rows = (len(s.frames) + cols - 1) // cols
    sheet = QImage(cols * (tw + 6) + 6, rows * (th + 6) + 6, QImage.Format.Format_RGB32)
    sheet.fill(QColor("#202024"))
    p = QPainter(sheet)
    p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
    for i, (img, t, c) in enumerate(zip(s.frames, s.times, s.changed)):
        x, y = 6 + (i % cols) * (tw + 6), 6 + (i // cols) * (th + 6)
        p.drawImage(QRect(x, y, tw, th), img)
        if c:
            p.setPen(QPen(QColor("#ff9500"), 3))
            p.drawRect(QRect(x + 1, y + 1, tw - 3, th - 3))
        p.fillRect(QRect(x, y, 64, 16), QColor(0, 0, 0, 170))
        p.setPen(QColor("white"))
        p.drawText(QRect(x + 4, y, 60, 16), Qt.AlignmentFlag.AlignVCenter, f"{t:.0f} ms")
    p.end()
    if not sheet.save(str(path)):
        raise RuntimeError(f"contact_sheet: could not save {path}")
    return str(path)
