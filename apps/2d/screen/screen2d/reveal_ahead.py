"""The eraser's reveal, drawn ahead: while the Eraser (or a smudging brush) is on and the selection holds paint, the world the canvas shows
without the layer it would erase (wet.py `without_paint`, `reveal_rect`) is asked of the canvas's engine before the pen
goes down, so the first eraser stroke shows at once like every brush's wet ink (it waited ~70-170 ms for this picture
at the press). Asked again, when the pointer is quiet, after anything it depends on changes: the document (a new
scene), the playhead, the selection, the view, the brush's mode. A press whose reveal is not the one kept asks for its
own, as before (painter._ask_reveal). Screen state only.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal
from rostrum_gui import pointer_quiet

from .wet import reveal_rect, without_paint

WAIT_MS = 120          # a burst of changes (a stroke landing, a pan) asks once, after it


class RevealAhead(QObject):
    _came = Signal(object, object, object)      # key, (pixels, origin), error: from the engine's worker thread

    def __init__(self, painter, bridge):
        super().__init__(painter)
        self.p, self.b = painter, bridge
        self._kept = None                         # (key, (pixels, origin)): the reveal drawn last
        self._asked = None                        # the key being drawn now
        self._timer = QTimer(self, singleShot=True, interval=WAIT_MS)
        self._timer.timeout.connect(self._ask)
        self._came.connect(self._take)
        for sig in (bridge.docChanged, bridge.timeChanged, bridge.selectedItemsChanged, bridge.toolChanged,
                    painter.brushChanged, bridge.world.changed):
            sig.connect(self.soon)

    def _target(self) -> tuple[str, bool] | None:
        """(the layer an eraser stroke would erase, through a painted fill?), or None when no stroke would erase."""
        p = self.p
        if self.b.tool != "draw" or not p._covering() or not p.canErase or self.b.opened.on or p._stroke is not None:
            return None
        through = p.through()
        d = through if through is not None else p._aim()
        return (d["id"], through is not None) if d else None

    def _key(self, target, x=None, y=None):
        visible = self.b.world.visible()
        if x is None:                             # ahead of a press: round the middle of the view
            x, y = (visible["x"] + visible["w"] / 2, visible["y"] + visible["h"] / 2) if visible else (0.0, 0.0)
        rect = reveal_rect(visible, x, y)
        return (id(self.b._scene), *target, self.b.time, self.b.play.samples(), tuple(rect.values())), rect

    def soon(self):
        if self._target() is not None:
            self._timer.start()

    def _ask(self):
        if pointer_quiet.busy():                  # never inside a click or a drag
            return self._timer.start()
        target = self._target()
        if target is None or not self.b._scene:
            return
        key, rect = self._key(target)
        if key in (self._asked, self._kept and self._kept[0]):
            return
        scene = without_paint(self.b._scene, *target)
        if scene is None:
            return
        self._asked, held = key, self.b._scene    # (held: the scene object the key names stays alive while drawn)
        self.b.frames.still(scene, self.b.time, self.b.play.samples(),
                            lambda px, e: self._came.emit((key, held), (px, (rect["x"], rect["y"])), e), rect)

    def _take(self, asked, got, error):
        key, _ = asked
        if key == self._asked:
            self._asked = None
        if error is None:                         # a failed one is said by the press that needs it (painter._reveal)
            self._kept = (key, got, asked[1])

    def ready(self, layer_id: str, fill: bool, x: float, y: float):
        """The kept reveal for an eraser pressed at x, y (world px) on `layer_id`, or None (not drawn yet, or stale)."""
        if self._kept is None:
            return None
        key, _ = self._key((layer_id, fill), x, y)
        return self._kept[1] if key == self._kept[0] else None
