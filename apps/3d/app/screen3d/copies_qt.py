"""Copies on the viewport, for QML as `viewport.copies` (brief 24): what the engine said about each copies item (how many
of its copies the shot camera sees: the grey line under Count), a click on one copy (the pick reply names it: the copies
item is selected and that copy is "Copy 7 of Buds"; the gizmo then moves that copy: copies_gizmo.py), and "On a surface…"
(the next click in the viewport names the surface: the same `copies.scatter` an agent calls). Screen state only: nothing
here is the document until the one change it makes.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from rostrum3d import copies_fields as CF

from . import outline
from .copies_actions import SURFACES, make_calls, SOURCES


def _plural(n: int) -> str:
    return f"{n} copy" if n == 1 else f"{n} copies"


def note_text(it: dict, got: dict, shot: str) -> str:
    """The grey line under Count: "212 of 400 in Hero 01" once the engine tested what the shot camera sees; "400 copies"
    when it did not (`got`: the scene reply's {count, seen, camera} for this item)."""
    n = got.get("count")
    if n is None and not (it.get("layout") == "surface" and it.get("amountBy") == "density"):
        n = it.get("count")                                     # the field's own, until the engine says how many
    if n is None:
        return ""
    if got.get("seen") is None:
        return _plural(int(n))
    return f"{got['seen']} of {n} in {shot}"


class CopiesTool(QObject):
    infoChanged = Signal()
    changed = Signal()                  # the picked copy changed (the gizmo moves to it)
    answered = Signal(object)           # (sources, the pick's reply or an error line) from the engine thread

    def __init__(self, bridge, viewport):
        super().__init__(viewport)
        self.b, self.v = bridge, viewport
        self.info: dict = {}            # {copies id: {count, seen, camera}}: the last scene reply's
        self.copy: dict | None = None   # the copy picked: {item, index, source, place}
        self.sources: list[str] = []    # "On a surface…" waits for the click that names the surface
        viewport._r.copiesInfo.connect(self._info)
        self.answered.connect(self._apply)
        bridge.selectionChanged.connect(self._selection)
        self.infoChanged.connect(bridge._refresh)

    # --- the grey line under Count
    def _info(self, info):
        info = dict(info or {})
        if info != self.info:
            self.info = info
            self.infoChanged.emit()

    def note(self, item_id: str) -> str:
        if not item_id or not self.b.doc.has(item_id):
            return ""
        return note_text(self.b.doc.item(item_id), self.info.get(item_id) or {}, self.b.shotInfo.get("label") or self.b.shot_id)

    # --- one copy picked
    def picked(self, item: str, reply) -> bool:
        """A pick's answer: True when it was a copy (the copies item selected, "Copy 7 of Buds"); the click is then done."""
        n = (reply or {}).get("copy")
        if n is None or not item or not self.b.doc.has(item) or self.b.doc.item(item)["type"] != "copies":
            if self.copy is not None:
                self.copy = None
                self.changed.emit()
            return False
        if item != self.b.selected:
            self.b.select(item)
        self.copy = {"item": item, "index": int(n), "source": reply.get("source", ""), "place": reply.get("place")}
        label = outline.label_of(self.b.doc.item(item))
        self.b.say(f"Copy {int(n) + 1} of {label}" + ("" if self.place() else "  ·  its place is not known yet: no handles"))
        self.changed.emit()
        return True

    def place(self) -> dict | None:
        """The picked copy's x y z rx ry rz s in its copies item's space: where it is held (the document), else the
        engine's `place` on the pick reply; a keyed copy's keyed fields at the playhead over that (where it is seen).
        None when it is not known. A copy still simulating gets its laid-out place (where its fall starts: what a move
        changes), not where it fell."""
        c = self.copy
        if c is None or not self.b.doc.has(c["item"]):
            return None
        held = CF.held_map(self.b.doc.item(c["item"])).get(c["index"])
        from .copies_gizmo import keyed_now, layout_place
        got = held or c.get("place") or layout_place(self.b.doc.item(c["item"]), c["index"])
        now = keyed_now(self.v.sent()[0], c["item"], c["index"], self.b.frame)
        if now and (got or len(now) == 6):
            got = {"s": 1.0, **(got or {}), **now}
        return dict(got) if got else None

    def _selection(self, *_):
        if self.copy is not None and self.b.selected != self.copy["item"]:
            self.copy = None
            self.changed.emit()
        if self.sources and list(self.b.selection) != self.sources:
            self.stop()

    # --- "On a surface…"
    def start_surface(self, sources: list[str]):
        self.sources = list(sources)
        self.b.say("Click the surface the copies stand on  ·  Esc to stop")

    def stop(self):
        if self.sources:
            self.sources = []
            self.b.say("")

    def wants_click(self) -> bool:
        return bool(self.sources)

    def click(self, x: float, y: float):
        scene, cam = self.v._pick_at(x, y)
        sources, self.sources = self.sources, []                # one click names it

        def job(eng):
            try:
                eng.ensure_scene(scene)
                self.answered.emit((sources, eng.pick(**cam)))
            except Exception as e:                              # loud, on the status line
                self.answered.emit((sources, str(e)))
        self.v._r.call(job)

    def _apply(self, answer):
        sources, r = answer
        doc = self.b.doc
        if isinstance(r, str):
            return self.b.fail_line(f"Error: scatter: {r}")
        item = r.get("item", "") if r.get("hit") else ""
        while item and doc.has(item) and doc.item(item)["type"] == "part":
            item = doc.parent_of(item)[0]
        if not item or not doc.has(item) or doc.item(item)["type"] not in SURFACES:
            return self.b.fail_line("Error: scatter: click a shape, import or clay to scatter the copies over.")
        sources = [s for s in sources if doc.has(s)]
        if not sources or any(doc.item(s)["type"] not in SOURCES for s in sources):
            return self.b.fail_line("Error: scatter: what to copy is no longer there; select it and try again.")
        from rostrum_core.tree import subtree_ids
        from rostrum3d.kind import KIND
        if item in sources or any(item in subtree_ids(doc.item(s), KIND.lists) for s in sources):
            return self.b.fail_line("Error: scatter: click a surface that is not what is being copied.")
        self.b.say("")
        self.b._act_apply(make_calls(doc, sources, "surface", item), "Scatter on a surface")
