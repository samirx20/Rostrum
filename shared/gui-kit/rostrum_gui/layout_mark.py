"""The layout check's picture: the window with each fault (layout_check.Fault) boxed in its kind's colour and
numbered as in the printed list."""
from __future__ import annotations

from PySide6.QtCore import QRectF

COLOURS = {"overlap": "#ff2d55", "cut": "#ff9500", "outside": "#af52de", "small": "#00c7be", "stray": "#ffd60a", "grid": "#5ac8fa",
           "zone": "#34c759"}


def mark(win, faults: list[Fault], path) -> None:
    """Save the window's picture with each fault boxed in its kind's colour and numbered as in the list."""
    from PySide6.QtGui import QColor, QFont, QPainter, QPen
    img = win.grabWindow()
    if img.isNull():
        raise RuntimeError("layout check: the window gave no picture")
    p = QPainter(img)
    p.setFont(QFont("Segoe UI", 9, QFont.Bold))
    for i, f in enumerate(faults, 1):
        c = QColor(COLOURS[f.kind])
        p.setPen(QPen(c, 2))
        r = QRectF(*f.rect).adjusted(-1, -1, 1, 1)
        p.drawRect(r)
        tag = QRectF(r.left(), max(0, r.top() - 14), 22, 14)
        p.fillRect(tag, c)
        p.setPen(QColor("white"))
        p.drawText(tag, 0x84, str(i))      # AlignCenter
    p.end()
    if not img.save(str(path)):
        raise RuntimeError(f"layout check: could not save {path}")
