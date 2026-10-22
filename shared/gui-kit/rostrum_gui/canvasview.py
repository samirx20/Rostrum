"""The canvas view, the ONE place for zoom, pan and view <-> canvas maths (INTERACTION.md 1.12). 2D's canvas, 3D's
view and the Editor's viewer all read it. The view is screen state: never a change, no undo step, never saved, and
an agent never moves it.

    view = canvas * zoom + pan          canvas = (view - pan) / zoom          (view px; canvas px)

What it does, in the focused view:
- Ctrl+wheel / pinch: zoom **around the pointer** (the canvas point under it stays under it). Wheel / Shift+wheel:
  scroll up and down / sideways.
- Space+drag and middle-drag: pan (`pans(button)` says whether a press pans; tapping Space still plays: the app's).
- The key map's view jobs (keymap.py; never key strings here): `zoom_in` / `zoom_out` a step, `fit_all` (Ctrl+0: the
  whole content), `actual_size` (Ctrl+1: 100 %), `fit` (F: the selection; nothing selected: everything).
- `place()` / `restore_place()` (view_place.py) and `menu()` / `pick()` (view_menu.py: the "Fit · 50 % ▾" control).
- `label` for the view controls: "Fit · 50 %" right after a fit, else "50 %".

Zoom stays within MIN_ZOOM .. MAX_ZOOM. A fit before the view has a size, or an empty box, fails loudly.
"""
from __future__ import annotations

import math

from PySide6.QtCore import Property, QObject, QPointF, Qt, Signal, Slot

from .keymap import SHARED
from .view_place import ViewPlace

MIN_ZOOM, MAX_ZOOM = 0.01, 64.0           # 1 % .. 6400 %
STEPS = (0.01, 0.02, 0.05, 0.1, 0.125, 0.25, 1 / 3, 0.5, 2 / 3, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 16.0, 32.0, 64.0)
FIT_PAD = 32.0                            # view px kept free round a fitted box
FIT_MOST = 4.0                            # F on a tiny item stops at 400 %
WHEEL_NOTCH = 120.0                       # Qt's angle delta for one wheel notch
NOTCH_ZOOM = 2 ** 0.25                    # one Ctrl+wheel notch: four notches double the zoom
JOBS = ("zoom_in", "zoom_out", "fit_all", "actual_size", "fit")

_missing = set(JOBS) - {r["job"] for r in SHARED}
if _missing:                              # the key map is the one source of view keys
    raise ImportError(f"canvasview: the key map has no job {', '.join(sorted(_missing))}")


def _clamp(z: float) -> float:
    return min(MAX_ZOOM, max(MIN_ZOOM, z))


class CanvasView(ViewPlace, QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._z, self._px, self._py, self._fitted = 1.0, 0.0, 0.0, False
        self._w = self._h = 0.0                          # the view's size, view px
        self._content = None                             # (x, y, w, h) canvas px: what Ctrl+0 fits
        self._selection = None                           # (x, y, w, h) canvas px: what F fits; None = nothing
        self._space, self._grab, self._fit_box = False, None, None   # _fit_box: the box last fitted to
        self._want_fit = False                           # a fitted place restored: fit once size and content are known (view_place.py)

    zoom = Property(float, lambda self: self._z, notify=changed)
    panX = Property(float, lambda self: self._px, notify=changed)
    panY = Property(float, lambda self: self._py, notify=changed)
    fitted = Property(bool, lambda self: self._fitted, notify=changed)

    @Property(str, notify=changed)
    def label(self):
        p = self._z * 100
        pct = f"{p:.1f}".rstrip("0").rstrip(".") if p < 20 else f"{round(p)}"
        return f"Fit · {pct} %" if self._fitted else f"{pct} %"

    # ---- what the view is showing ---------------------------------------------------------------------------
    @Slot(float, float)
    def setViewSize(self, w, h):
        """The view's size in view px; a fitted view fits again, so it follows the window."""
        self._w, self._h = float(w), float(h)
        if self._fitted and self._fit_box is not None and w > 0 and h > 0:
            self.fit_box(self._fit_box)
        self._refit()

    @Slot(float, float, float, float)
    def setContent(self, x, y, w, h):
        """The whole content in canvas px (the frame, the cut): what Ctrl+0 fits."""
        self._content = (x, y, w, h)
        self._refit()

    @Slot(float, float, float, float)
    def setSelection(self, x, y, w, h):
        """The selection's box in canvas px (w or h <= 0: nothing selected): what F fits."""
        self._selection = (x, y, w, h) if w > 0 and h > 0 else None

    # ---- the maths ------------------------------------------------------------------------------------------
    def to_view(self, cx: float, cy: float) -> tuple[float, float]:
        return cx * self._z + self._px, cy * self._z + self._py

    def to_canvas(self, vx: float, vy: float) -> tuple[float, float]:
        return (vx - self._px) / self._z, (vy - self._py) / self._z

    @Slot(float, float, result="QPointF")
    def toView(self, cx, cy):
        return QPointF(*self.to_view(cx, cy))

    @Slot(float, float, result="QPointF")
    def toCanvas(self, vx, vy):
        return QPointF(*self.to_canvas(vx, vy))

    # ---- zoom -----------------------------------------------------------------------------------------------
    @Slot(float, float, float)
    def zoomAt(self, zoom, vx, vy):
        """Zoom to `zoom` keeping the canvas point under (vx, vy) where it is."""
        if not math.isfinite(zoom) or zoom <= 0:
            raise ValueError(f"canvas view: a zoom must be above 0 (got {zoom!r})")
        cx, cy = self.to_canvas(vx, vy)
        self._z = _clamp(zoom)
        self._set(vx - cx * self._z, vy - cy * self._z)

    @Slot(float, float, float)
    def zoomBy(self, factor, vx, vy):
        """Pinch, or anything that scales the zoom, around (vx, vy)."""
        self.zoomAt(self._z * factor, vx, vy)

    @Slot(float, float, float, float, int)
    def wheel(self, ax, ay, vx, vy, modifiers):
        """A wheel turn (Qt's angleDelta) at (vx, vy): Ctrl zooms around the pointer, Shift scrolls sideways,
        plain scrolls up and down."""
        if modifiers & Qt.ControlModifier.value:
            self.zoomBy(NOTCH_ZOOM ** (ay / WHEEL_NOTCH), vx, vy)
        elif modifiers & Qt.ShiftModifier.value:
            self.panBy(ay or ax, 0.0)
        else:
            self.panBy(ax, ay)

    def _step(self, up: bool):
        z = self._z
        nxt = [s for s in STEPS if s > z * 1.001] if up else [s for s in STEPS if s < z / 1.001]
        target = (nxt[0] if up else nxt[-1]) if nxt else z
        self.zoomAt(target, self._w / 2, self._h / 2)

    def fit_box(self, box) -> None:
        if not self._w or not self._h:
            raise ValueError("canvas view: can't fit before the view has a size (setViewSize)")
        x, y, w, h = box
        if w <= 0 or h <= 0:
            raise ValueError(f"canvas view: can't fit an empty box ({w} × {h})")
        self._z = _clamp(min((self._w - 2 * FIT_PAD) / w, (self._h - 2 * FIT_PAD) / h, FIT_MOST))
        self._fit_box = box
        self._set(self._w / 2 - (x + w / 2) * self._z, self._h / 2 - (y + h / 2) * self._z, fitted=True)

    @Slot(str)
    def job(self, name):
        """Run one of the key map's view jobs (the screen's shortcuts and the view controls' menu call this)."""
        if name not in JOBS:
            raise ValueError(f'canvas view: "{name}" is not a view job; use one of: {", ".join(JOBS)}')
        if name in ("zoom_in", "zoom_out"):
            self._step(name == "zoom_in")
        elif name == "actual_size":
            self.zoomAt(1.0, self._w / 2, self._h / 2)
        elif name == "fit" and self._selection is not None:
            self.fit_box(self._selection)
        else:                                             # fit_all, or F with nothing selected
            if self._content is None:
                raise ValueError("canvas view: nothing to fit yet (setContent)")
            self.fit_box(self._content)

    # ---- pan ------------------------------------------------------------------------------------------------
    @Slot(float, float)
    def panBy(self, dx, dy):
        self._set(self._px + dx, self._py + dy)

    @Slot(bool)
    def setSpace(self, held):
        """Space is held (a press with it pans; a tap without a drag is the app's play)."""
        self._space = bool(held)

    @Slot(int, result=bool)
    def pans(self, button):
        """Does a press with this mouse button pan? Middle always; any with Space held."""
        return button == Qt.MiddleButton.value or self._space

    @Slot(float, float)
    def panPress(self, vx, vy):
        self._grab = (vx, vy)

    @Slot(float, float)
    def panMove(self, vx, vy):
        if self._grab is not None:
            gx, gy = self._grab
            self._grab = (vx, vy)
            self.panBy(vx - gx, vy - gy)

    @Slot()
    def panRelease(self):
        self._grab = None

    def _set(self, px: float, py: float, fitted: bool = False):
        self._px, self._py, self._fitted = px, py, fitted
        self.changed.emit()
