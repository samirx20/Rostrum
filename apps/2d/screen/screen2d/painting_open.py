"""A painting opened on its own (design 2d-painted-fill § 3.4, mock-4): entered and left like going inside a symbol, for
tiling work. The canvas shows the painting at world (0, 0), its own px being world px (so the pen, Fill, Select strokes
and the eraser need no mapping: `place` is the identity), outlined, its size above it; a seamless painting shows its
repeats all round, a little darker. The settings panel paints on it (painter.target), the timeline shows its one row
(its drawings as cells when it draws each frame), the path chip says "Autumn menu › Paper grain".

Entering keeps the selection and the tool and leaves them as they were; Esc, V or the chip's scene name goes back.
The picture shown is the painting kit's own content-keyed PNG of the drawing at the playhead (drawing.picture), the
very file every use and the export read; made off the screen's thread when it is new (paint_pictures.py), the last one
standing in meanwhile. Screen state only: opening is no change to the document. Read in QML as `backend.opened`.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from rostrum2d import drawing as D, paintings
from rostrum2d.names import display_name

from . import fill_aim, framing, outline
from .paint_pictures import PaintPictures

STAYS = ("draw", "hand", "zoom")        # tools that keep the painting open (painting, moving the view)


def place(painting: dict) -> dict:
    """The painting's place on the opened canvas: its px are world px from (0, 0) (placement.py's form)."""
    w, h = D.canvas_size(painting)
    return {"m": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0], "w": float(w), "h": float(h),
            "edge": f"M0 0 L{w} 0 L{w} {h} L0 {h} Z"}


def row(painting: dict, fps: float, duration: float) -> dict:
    """The timeline's one row while it is open: its drawings as cells when it draws each frame (FrameMarks.qml), no
    bar (a painting has no time of its own: each use runs it from its own start)."""
    out = outline._row("layer", painting, 0, outline.label_of(painting), [])
    if D.each_frame(painting):
        out.update(frames=framing.marks(painting, fps, duration), again=framing.again(painting, fps, duration))
    return out


class OpenedPainting(QObject):
    changed = Signal()
    landed = Signal()               # the picture with the newest strokes is shown (the wet ink may go)

    def __init__(self, bridge):
        super().__init__(bridge)
        self.b, self._id, self._before = bridge, "", None     # _before: (selection, tool) to go back to
        self._picture, self._shows, self._told = "", None, None
        self._info = None                   # (document data, painting id, info): `info`
        self._pictures = PaintPictures(self)
        self._pictures.done.connect(self._made)
        self._pictures.failed.connect(bridge._fail)
        bridge.docChanged.connect(self._doc)
        bridge.timeChanged.connect(self._look)
        bridge.toolChanged.connect(self._tool)

    # ---- reads -------------------------------------------------------------------------------------------------
    def item(self) -> dict | None:
        """The painting open now, as the document has it (None: none open)."""
        if not self._id or not self.b.doc.has(self._id):
            return None
        return self.b.doc.item(self._id)

    def frame(self) -> int:
        """The frame the painting is shown and painted at: the playhead's (an opened painting runs from 0)."""
        return D.frame_number(self.b.time, self.b.comp()["fps"])

    on = Property(bool, lambda self: bool(self._id), notify=changed)
    id = Property(str, lambda self: self._id, notify=changed)
    picture = Property(str, lambda self: self._picture, notify=changed)

    @Property("QVariantMap", notify=changed)
    def info(self):
        """{name, w, h, seamless, eachFrame, loop, scene, sub, uses: [{id, name}]}; {} when none is open. Worked out once
        per document state (a document is never changed in place): QML reads it ~30 times as a painting opens, and
        each finding its uses walked the whole scene."""
        p = self.item()
        if p is None:
            return {}
        if self._info is None or self._info[0] is not self.b.doc.data or self._info[1] != self._id:
            self._info = (self.b.doc.data, self._id, self._info_of(p))
        return self._info[2]

    def _info_of(self, p: dict) -> dict:
        w, h = D.canvas_size(p)
        uses = [{"id": u["id"], "name": display_name(u)} for u in fill_aim.users(self.b.doc, p["id"])]
        used = f"used by {len(uses)} layer{'s' if len(uses) != 1 else ''}" if uses else "not used yet"
        return {"name": p.get("name", "Painting"), "w": w, "h": h, "seamless": paintings.seamless(p),
                "eachFrame": D.each_frame(p), "loop": p.get("loop", "loop"), "scene": outline.label_of(self.b.comp()),
                "sub": f'{p.get("name", "Painting")} · {w} × {h} · {used}', "uses": uses}

    # ---- going in and out --------------------------------------------------------------------------------------
    @Slot(str)
    def open(self, painting_id):
        """Open a painting on its own: the brush on, nothing picked (both as they were when it closes)."""
        if not self.b.doc.has(painting_id) or self.b.doc.item(painting_id)["type"] != "painting":
            return self.b._fail(f'Error: open painting: no painting "{painting_id}" in this scene')
        if self._before is None:
            self._before = (list(self.b.selection), self.b.tool)
        self._id = painting_id
        self.b.clearSelection()
        self.b.paintTool.use("brush")
        self._look()
        self._tell(True)
        self.b._set_status(f"Painting {self.info['sub']}")

    @Slot()
    def close(self):
        """Back to the scene, picking and tool as they were."""
        self._leave(True, True)

    @Slot(str)
    def goToUse(self, layer_id):
        """Used by › a name: back to the scene with that layer picked."""
        self._leave(False, True)
        self.b.select(layer_id)

    def _leave(self, picks: bool, tool: bool):
        """Back to the scene: the picking as it was (`picks`), the tool as it was (`tool`)."""
        if not self._id:
            return
        before, self._id, self._before = self._before, "", None
        self._picture, self._shows = "", None
        self._tell(True)
        self.b._set_status("")
        if before is not None:
            if picks:
                self.b.selectMany([i for i in before[0] if self.b.doc.has(i)])
            if tool:
                self.b.setTool(before[1])

    def _tool(self):
        if self._id and self.b.tool not in STAYS:      # V, Esc, a creation tool: back to the scene with that tool
            self._leave(True, False)

    # ---- the picture ---------------------------------------------------------------------------------------------
    def _doc(self, *_):
        if self._id and self.item() is None:            # undone or deleted while open: back to the scene
            return self._leave(True, True)
        self._look()

    def _look(self):
        p = self.item()
        if p is None:
            return
        shown = D.frame_at(p, self.frame()) if D.each_frame(p) else (p["frames"][0] if p.get("frames") else None)
        if shown is None:
            return self._show("", None)
        later: list = []
        path = D.picture(p, shown, later)
        if later:                                        # made off this thread; the last picture stands in
            self._pictures.make(later, (p, shown))
            if not self._picture:
                self._show(path, None)
        else:
            self._show(path, shown)

    def _made(self, token):
        if self.item() is token[0]:
            self._look()

    def _show(self, path, shown):
        url = QUrl.fromLocalFile(str(path)).toString() if path else ""
        self._shows = shown
        if url != self._picture:
            self._picture = url
            self._tell(True)
        else:
            self._tell()
        if shown is not None:
            self.landed.emit()

    def shows_now(self) -> bool:
        """The picture shown is of the document as it is (no newer strokes still being made)."""
        p = self.item()
        if p is None:
            return True
        now = D.frame_at(p, self.frame()) if D.each_frame(p) else (p["frames"][0] if p.get("frames") else None)
        return now is None or self._shows is now

    def _tell(self, force=False):
        told = (self._id, self._picture, self.info if self._id else None)
        if force or told != self._told:
            went = self._told is None or told[0] != self._told[0]
            self._told = told
            self.changed.emit()
            if went:                                    # in or out: the timeline's rows and the panel follow
                self.b._layers_check()
                self.b.painter._refresh()

    def close_down(self):
        self._pictures.close()
