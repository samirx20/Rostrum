"""Paint mode's Brush group, for QML as `paintMode.brush` (SPEC §5, mockup 06): the kit's bar settings
(rostrum_paint.fields.BAR: tip, size, colour, opacity) as the kit's own rows, so InspectorRow draws them exactly as it
draws any field (it talks to this object as its `bridge`). The brush is screen state, never in the document: each
stroke stores every setting it was painted with (the kit's stroke.add), so changing the brush changes the next stroke.

While stamping (`stamping`: Stamp on a Relief layer, paint_mode_qt) the rows are the stamp's instead: Picture (the
kit's tip pictures, ending with "Load picture…" when the scene is in a project), Size (the brush's own), Depth and
Turn (paint.stamp's params). The stamp's picture, depth and turn are kept apart (`stamp`), never in a stroke.
"""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum3d import paint_stamp_pictures
from rostrum3d.ops_paint_stamp import DEPTH, TURN
from rostrum_core import RostrumError
from rostrum_gui import rows
from rostrum_gui.model import RowsModel
from rostrum_paint import library
from rostrum_paint.fields import BRUSH

from . import paint_mode as P

_OP = SimpleNamespace(params=P.BAR_PARAMS)
PICTURES = "Pictures (*.png *.jpg *.jpeg *.webp *.tif *.tiff *.bmp)"


def _stamp_params(folder=None) -> list:
    """Picture, Size, Depth, Turn under one Stamp heading; the picture's choices as the kit has them now (a brush tip's
    padded stamp copy left out: the tip itself is listed, and stamps as its copy)."""
    texture, size = (next(p for p in BRUSH if p.name == n) for n in ("texture", "size"))
    gone = {"none", *paint_stamp_pictures.hidden(folder)}
    return [replace(texture, label="Picture", group="Stamp", importance="primary",
                    options=[o for o in texture.options if o not in gone],
                    labels={k: v for k, v in (texture.labels or {}).items() if k not in gone},
                    help="The picture laid whole with one click: bright raises, dark stays flat (a picture with "
                         "see-through parts raises where it is opaque)"),
            replace(size, group="Stamp", help="The picture's width (its longest side), in px of the paint picture (of "
                                               "the screen on a mesh or From the view)"),
            DEPTH, TURN]


class PaintBrush(QObject):
    changed = Signal()

    def __init__(self, parent=None, folder=lambda: None, fail=print):
        super().__init__(parent)
        self._fail = fail                               # a picture that can't be loaded: said on the status line
        self.values = P.start_brush()
        self.stamp = P.start_stamp()
        self.stamping, self._folder, self._gen = False, folder, None
        self.model = RowsModel(rows.ROLES, self)
        self._static = rows.layout(_OP)
        self.model.reset(self._rows())

    def _params(self):
        return _stamp_params(self._folder()) if self.stamping else P.BAR_PARAMS

    def _rows(self):
        if not self.stamping:
            return rows.evaluate(self._static, self.values, {}, False)
        if self._gen != library.generation:              # the project's own pictures changed: new choices
            self._static, self._gen = rows.layout(SimpleNamespace(params=_stamp_params(self._folder()))), library.generation
        out = rows.evaluate(self._static, {**self.values, **self.stamp}, {}, False)
        if self._folder():                              # a loaded picture is kept in the project
            for r in out:
                if r["row"] == "param" and r["id"] == "texture":
                    r["more"], r["filters"] = "Load picture…", [PICTURES]
        return out

    def set_stamping(self, on: bool):
        if on != self.stamping:
            self.stamping = on
            if on and self._folder():
                library.use_project(self._folder())     # the project's own pictures are choices
            self._static = rows.layout(_OP) if not on else rows.layout(SimpleNamespace(params=_stamp_params(self._folder())))
            self._gen = library.generation
            self.model.reset(self._rows())
            self.changed.emit()

    def _set(self, name, value):
        p = next((q for q in self._params() if q.name == name), None)
        if p is None:
            return False
        try:
            v = p.check(round(value, 4) if isinstance(value, float) else value, f"brush.{name}")
        except RostrumError as e:                 # a value out of range: said on the row, the brush unchanged
            print(e.line())
            return False
        (self.stamp if name in self.stamp else self.values)[name] = v
        self.model.update(self._rows())
        self.changed.emit()
        return True

    rows = Property(QObject, lambda s: s.model, constant=True)
    size = Property(float, lambda s: float(s.values["size"]), notify=changed)
    colour = Property(str, lambda s: s.values["color"], notify=changed)

    # --- InspectorRow's bridge
    @Slot(str, "QVariant", result=bool)
    def setValue(self, name, value):
        return self._set(name, value)

    @Slot(str, str, result=bool)
    def loadChoice(self, name, path):
        """Load picture… on the stamp's Picture: the file is kept in the project as a relief tip (brightness = height,
        its padded copy, paint_stamp_pictures.prepare) and becomes the picture; the list grows by itself."""
        try:
            self.stamp["texture"] = paint_stamp_pictures.prepare(self._folder(), path)[0]
        except RostrumError as e:
            self._fail(e.line())
            return False
        self._static = rows.layout(SimpleNamespace(params=_stamp_params(self._folder())))
        self._gen = library.generation
        self.model.reset(self._rows())
        self.changed.emit()
        return True

    @Slot(str)
    def beginScrub(self, name):
        pass

    @Slot(str, "QVariant")
    def scrub(self, name, value):
        self._set(name, value)

    @Slot()
    def endScrub(self):
        pass

    @Slot()
    def cancelScrub(self):
        pass

    @Slot(str)
    def toggleGroup(self, group):
        pass

    @Slot(str)
    def toggleAnimate(self, name):
        pass
