"""The shipped brushes (painting design §3.2): each preset is only settings the painting kit already has
(`rostrum_paint.fields.BRUSH`), never a colour (the colour is the person's). The brush panel (BrushFlyout.qml) shows
each as a real stroke, painted by the kit's own engine (`preview`), served to QML as image://brushes/<id>.
A read-only table for now; saved brushes (a project library item) come later (design §5, P6).
"""
from __future__ import annotations

import threading

import numpy as np
from PySide6.QtGui import QImage
from PySide6.QtQuick import QQuickImageProvider
from rostrum_paint.brush import stamp_stroke
from rostrum_paint.fields import brush_defaults
from rostrum_paint.marks import Paper

GROUPS = ("Sketch", "Ink", "Paint", "Light", "Texture")
DEFAULT = "hard"
# (id, name, group, size, settings): the settings a preset sets; every other brush setting goes back to its default
PRESETS = [
    ("pencil", "Pencil", "Sketch", 5, dict(brush="chalk", hardness=.75, grain=.55, opacity=.9, size_pressure=.3, opacity_pressure=.8, color_jitter=0)),
    ("charcoal", "Charcoal", "Sketch", 16, dict(brush="chalk", hardness=.3, grain=.8, opacity=.95, size_pressure=.5, opacity_pressure=.8, color_jitter=.02, texture="charcoal")),
    ("rough", "Rough line", "Sketch", 4, dict(brush="round", hardness=.6, opacity=.55, size_pressure=.5, opacity_pressure=.6, jitter=.06, color_jitter=0)),
    ("ink", "Ink pen", "Ink", 8, dict(brush="line", hardness=1, size_pressure=1, opacity_pressure=0, color_jitter=0)),
    ("mono", "Fine liner", "Ink", 4, dict(brush="line", hardness=1, size_pressure=0, opacity_pressure=0, color_jitter=0)),
    ("brushpen", "Brush pen", "Ink", 12, dict(brush="round", hardness=.92, spacing=.05, size_pressure=1, opacity_pressure=0, color_jitter=0)),
    ("dryink", "Dry ink", "Ink", 14, dict(brush="bristle", hardness=.85, spacing=.06, size_pressure=.85, opacity_pressure=.1, color_jitter=0)),
    ("hard", "Round hard", "Paint", 22, dict(brush="round", hardness=.9, size_pressure=.4, opacity_pressure=.2, color_jitter=.02)),
    ("air", "Airbrush", "Paint", 46, dict(brush="round", hardness=0, opacity=.35, spacing=.03, size_pressure=0, opacity_pressure=1, color_jitter=0)),
    ("oil", "Bristle oil", "Paint", 30, dict(brush="bristle", hardness=.6, color_jitter=.1, hue_jitter=3, size_pressure=.5, opacity_pressure=.4)),
    ("flat", "Flat", "Paint", 30, dict(brush="flat", hardness=.7, color_jitter=.06, size_pressure=.3, opacity_pressure=.3)),
    ("gouache", "Gouache block", "Paint", 34, dict(brush="block", hardness=.9, color_jitter=.05, size_pressure=.2, opacity_pressure=.1)),
    ("blend", "Wet blend", "Paint", 30, dict(brush="round", hardness=.4, smudge=True, wet=.6, opacity=.7, size_pressure=.3, opacity_pressure=.5)),
    ("wetbristle", "Wet bristle", "Paint", 28, dict(brush="bristle", hardness=.6, smudge=True, wet=.35, color_jitter=.08, size_pressure=.5)),
    ("glaze", "Glaze", "Light", 44, dict(brush="round", hardness=.1, mode="multiply", opacity=.6, spacing=.03, size_pressure=0, opacity_pressure=.8)),
    ("glow", "Glow", "Light", 44, dict(brush="round", hardness=0, mode="add", opacity=.3, spacing=.03, size_pressure=0, opacity_pressure=.8)),
    ("chalk", "Pastel", "Texture", 26, dict(brush="chalk", hardness=.5, grain=.6, opacity_pressure=.6, color_jitter=.05)),
    ("scumble", "Dry brush", "Texture", 30, dict(brush="bristle", hardness=.5, grain=.45, opacity=1, spacing=.15, color_jitter=.06, texture="streaks")),
    ("spatter", "Spatter", "Texture", 5, dict(brush="round", hardness=.85, jitter=1.6, spacing=.9, size_pressure=.6, opacity_pressure=0, color_jitter=.1)),
]
BY_ID = {p[0]: p for p in PRESETS}


def name(pid: str) -> str:
    return BY_ID[pid][1] if pid in BY_ID else "Custom brush"


def settings(pid: str) -> dict:
    """The brush settings preset `pid` sets: every setting but colour and seed, defaults where it says nothing."""
    _, _, _, size, own = BY_ID[pid]
    out = {k: v for k, v in brush_defaults().items() if k not in ("color", "seed")}
    return {**out, "size": float(size), **own}


def matches(pid: str, values: dict) -> bool:
    """The brush is still exactly preset `pid` (no setting changed since it was picked)."""
    return pid in BY_ID and all(values.get(k) == v for k, v in settings(pid).items())


def groups() -> list[dict]:
    """[{group, presets: [{id, name}]}], in the panel's order."""
    return [{"group": g, "presets": [{"id": p[0], "name": p[1]} for p in PRESETS if p[2] == g]} for g in GROUPS]


# ---- previews: a short S-stroke, light -> firm -> light, painted by the kit's engine ----------------------------
W, H, INK, BG = 232, 56, (0.93, 0.90, 0.84), (0.137, 0.141, 0.157)


def _points(pad=14):
    xs = np.linspace(pad, W - pad, 60)
    ys = H / 2 + (H / 2 - pad) * 0.55 * np.sin((xs - pad) / (W - 2 * pad) * 2 * np.pi)
    pr = np.sin(np.linspace(0.08, np.pi - 0.08, 60)) ** 0.7
    return [(float(x), float(y), float(p)) for x, y, p in zip(xs, ys, pr)]


def _lay():
    from rostrum_paint import native   # not built: the Python stamper paints the same pixels, only slower; out of
    return native.lay if native.available() else None   # date: native.OutOfDate, loudly (never a quiet fallback)


def preview(pid: str) -> QImage:
    """Preset `pid`'s stroke on the panel's dark ground, W x H. Wet brushes get two bands of paint to drag;
    multiply and add get a ground to show what they do."""
    _, _, _, size, s = BY_ID[pid]
    layer, under, ink, lay = np.zeros((H, W, 4), np.float32), np.broadcast_to(np.array(BG, np.float32), (H, W, 3)).copy(), INK, _lay()
    params = {k: v for k, v in s.items() if k not in ("brush", "smudge") and (k != "wet" or s.get("smudge"))}
    if s.get("smudge"):
        for i, c in enumerate([(0.85, 0.45, 0.30), (0.30, 0.45, 0.85)]):
            y = H * (0.33 + 0.34 * i)
            stamp_stroke(layer, [(10, y, 1), (W - 10, y, 1)], c, 18, "round", hardness=.9, color_jitter=0, lay=lay)
    if s.get("mode") == "multiply":
        stamp_stroke(layer, [(10, H / 2, 1), (W - 10, H / 2, 1)], (0.85, 0.75, 0.55), 40, "block", hardness=.9, color_jitter=0, lay=lay)
        ink = (0.45, 0.35, 0.65)
    elif s.get("mode") == "add":
        ink = (0.95, 0.55, 0.25)
    stamp_stroke(layer, _points(), ink, size, s.get("brush", "round"), under=under, paper=Paper(H, W), seed=7, lay=lay, **params)
    a = layer[..., 3:]
    rgb = np.clip(under + layer[..., :3], 0, 1) if s.get("mode") == "add" else layer[..., :3] + (1 - a) * under
    px = np.ascontiguousarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))
    return QImage(px.data, W, H, 3 * W, QImage.Format.Format_RGB888).copy()


class PreviewProvider(QQuickImageProvider):
    """image://brushes/<id>: painted once per run, on QML's loader thread (Image { asynchronous: true })."""

    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Image)
        self._lock, self._made = threading.Lock(), {}

    def requestImage(self, id_, size, requested):  # noqa: N802 (Qt's name)
        pid = id_.split("?")[0]
        with self._lock:
            if pid not in self._made:
                if pid not in BY_ID:
                    raise KeyError(f"no brush preset {pid!r}")
                self._made[pid] = preview(pid)
            return self._made[pid]
