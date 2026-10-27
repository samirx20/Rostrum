"""The canvas pointer set (CANVAS.md 1.2, CURSORS.md): our own pointers, drawn from the SVGs in icons/cursors/, so the
pointer shows what a press will do right there. Every canvas in every app uses these; never Qt's stock shapes there.

    KINDS                        the shapes and each one's hotspot (design px in the 24 px design; the press lands
                                 in that pixel). Even numbers, so the hotspot stays a whole pixel at 1.5x too
    BADGES                       the small marks a shape can carry (bottom-right; `centre` sits on the hotspot)
    cursor(kind, angle, badge, scale, dpr)   the QCursor, made once and kept: the angle snaps to 5° steps and the
                                 shape turns about its hotspot, so the hotspot stays exact; a badge never turns
    picture(kind, angle, badge, scale)       the same drawing as (QImage, hotspot QPoint): the cursor sheet uses it
    scale_for(window)            1, 1.5 or 2: the screen's size step (the kit draws its windows at 1x, so a 150 %
                                 screen still gets 1.5x pointers, the same size as the system's own arrow)

An unknown kind or badge raises ValueError: a pointer never quietly falls back to something else. `none` is the
hidden pointer, only for painting tools that draw their own ring (CANVAS 1.1)."""
from __future__ import annotations

import math
import re
from pathlib import Path

ICONS = Path(__file__).resolve().parent.parent / "icons" / "cursors"
THEME = Path(__file__).resolve().parent.parent / "qml" / "RostrumKit" / "Theme.qml"
SIZE = 24                     # the design's size, px at 1x
STEP = 5                      # degrees: a turned pointer snaps to these
SCALES = (1.0, 1.5, 2.0)

KINDS = {                     # name: hotspot (x, y) in the 24 px design
    "pick": (4, 2),           # the arrow's tip: pick and move
    "resize": (12, 12),       # two-headed arrow, angle = the handle's direction (0 = right, clockwise)
    "rotate": (12, 12),       # curved two-headed arrow bowing towards the angle (0 = a handle on the right)
    "anchor": (12, 12),       # ring with four ticks: the anchor point
    "text": (12, 12),         # I-beam
    "text-box": (12, 12),     # cross with a small box: Text tool on empty canvas
    "make": (12, 12),         # thin cross: draw something new
    "pen": (4, 2),            # the nib's tip
    "fill": (6, 20),          # where the paint drop lands
    "dropper": (2, 22),       # the dropper's tip
    "hand": (12, 12),         # move the view, and nothing else
    "hand-grab": (12, 12),    # moving the view
    "zoom-plus": (10, 10),    # the lens's centre
    "zoom-minus": (10, 10),
    "no": (12, 12),           # a press here would do nothing (the status line says why on press)
    "none": None,             # hidden: a painting tool's own ring is the pointer
}
BADGES = {                    # name: where it sits
    "copy": "corner", "remove": "corner", "deep": "corner", "point": "corner", "bend": "corner",
    "radius": "corner", "shape": "corner", "close": "corner", "x": "corner", "caret": "corner",
    "slash": "corner", "wrap": "corner", "alt": "corner", "centre": "hotspot",
}
BADGE_SIZE, BADGE_AT = 10, 14          # a badge is 10 px, its corner at (14, 14) in the design

_made: dict = {}
_svgs: dict = {}


def check(kind: str, badge: str = "") -> None:
    if kind not in KINDS:
        raise ValueError(f"unknown pointer kind {kind!r}; the kinds are {', '.join(KINDS)}")
    if badge and badge not in BADGES:
        raise ValueError(f"unknown pointer badge {badge!r}; the badges are {', '.join(BADGES)}")


def snap(angle: float) -> int:
    """The 5° step an angle shows as (0..71)."""
    return int(round(float(angle) / STEP)) % (360 // STEP)


def scale_for(window) -> float:
    dpr = window.devicePixelRatio() if window is not None else 1.0
    screen = window.screen() if window is not None else None
    if abs(dpr - 1.0) < 0.01 and screen is not None:   # the kit's windows draw at 1x (app.start): the screen's own step
        dpr = screen.logicalDotsPerInch() / 96.0
    return min(SCALES, key=lambda s: abs(s - dpr))


def _colours() -> dict:
    """Badge colours come from Theme.qml (one place): the files carry today's accent and danger as written."""
    text = THEME.read_text(encoding="utf-8")
    out = {}
    for name, was in (("accent", "#4c8dff"), ("danger", "#ff6b6b")):
        m = re.search(rf'property color {name}:\s*"(#[0-9a-fA-F]+)"', text)
        if m:
            out[was] = m.group(1)
    return out


def _svg(name: str):
    from PySide6.QtCore import QByteArray
    from PySide6.QtSvg import QSvgRenderer
    if name not in _svgs:
        path = ICONS / f"{name}.svg"
        data = path.read_text(encoding="utf-8")       # a missing file raises: loud
        for was, now in _colours().items():
            data = data.replace(was, now)
        r = QSvgRenderer(QByteArray(data.encode("utf-8")))
        if not r.isValid():
            raise ValueError(f"pointer drawing {path} does not load")
        _svgs[name] = r
    return _svgs[name]


def picture(kind: str, angle: float = 0, badge: str = "", scale: float = 1.0):
    """(QImage, QPoint hotspot) at `scale` device px per design px. The shape turns about its hotspot pixel's centre;
    the canvas is cut on whole pixels round it, so the hotspot is exact at every angle."""
    from PySide6.QtCore import QPoint, QRectF, Qt
    from PySide6.QtGui import QImage, QPainter
    check(kind, badge)
    hx, hy = KINDS[kind]
    deg = snap(angle) * STEP
    px, py = (hx + 0.5) * scale, (hy + 0.5) * scale             # the pivot: the hotspot pixel's centre
    side = SIZE * scale
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    xs, ys = [], []
    for x, y in ((0, 0), (side, 0), (0, side), (side, side)):
        dx, dy = x - px, y - py
        xs.append(px + dx * c - dy * s)
        ys.append(py + dx * s + dy * c)
    if badge:
        box = _badge_box(badge, hx, hy, scale)
        xs += [box.left(), box.right()]
        ys += [box.top(), box.bottom()]
    left, top = math.floor(min(xs) + 1e-6), math.floor(min(ys) + 1e-6)
    w, h = math.ceil(max(xs) - 1e-6) - left, math.ceil(max(ys) - 1e-6) - top
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.translate(-left, -top)
    p.translate(px, py)
    p.rotate(deg)
    p.translate(-px, -py)
    _svg(kind).render(p, QRectF(0, 0, side, side))
    if badge:
        p.resetTransform()
        p.translate(-left, -top)
        _svg(f"badge-{badge}").render(p, _badge_box(badge, hx, hy, scale))
    p.end()
    return img, QPoint(math.floor(px) - left, math.floor(py) - top)


def _badge_box(badge, hx, hy, scale):
    from PySide6.QtCore import QRectF
    b = BADGE_SIZE * scale
    if BADGES[badge] == "hotspot":
        return QRectF((hx + 0.5) * scale - b / 2, (hy + 0.5) * scale - b / 2, b, b)
    return QRectF(BADGE_AT * scale, BADGE_AT * scale, b, b)


def cursor(kind: str, angle: float = 0, badge: str = "", scale: float = 1.0, dpr: float = 1.0):
    """The QCursor (kept: the same object every time for the same kind, 5° step, badge, scale and window dpr)."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QCursor, QPixmap
    check(kind, badge)
    key = (kind, snap(angle), badge, scale, dpr)
    if key not in _made:
        if KINDS[kind] is None:
            _made[key] = QCursor(Qt.CursorShape.BlankCursor)
        else:
            img, hot = picture(kind, angle, badge, scale)
            pix = QPixmap.fromImage(img)
            pix.setDevicePixelRatio(dpr)
            _made[key] = QCursor(pix, round(hot.x() / dpr), round(hot.y() / dpr))
    return _made[key]
