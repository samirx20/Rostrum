"""A canvas drag of several layers, moved without changing the document on every move: the moves are checked once at
the press (the same operations as the release, on the state at the press: locked, driven by an expression, x / y not
valid now all refuse there), each move then only tells the engine the layers' new places (ENGINE_CONTRACT.md `edit`)
and shows the outlines on a light copy of the document, and the release applies the one change (one undo step). 200
layers: each move planned, described and checked whole cost ~60-90 ms; this is a few.

Not for a layer whose x or y is keyed (a move there keys at the playhead: the keys the engine draws would change), one
the picture doesn't draw (hidden: no node to edit), nor a camera-key drag holding the view: those drags go through drags.moveBy's per-move change as before. Nothing reads the document's moved values mid-drag:
the timeline and the panel follow at the drop (drags.moving_many), the outlines read the picture's tag (shown.py)."""
from __future__ import annotations

from rostrum_core import run
from rostrum_core.keys import keys_of
from rostrum_core.tree import child_keys

from . import route


class GhostMove:
    def __init__(self, b, grab):
        self.b, self.grab, self.at, self.moved = b, grab, (0.0, 0.0), False

    @classmethod
    def start(cls, b, grab):
        """The ghost for this grab [(layer, x0, y0)], or None (the drag goes the per-move way)."""
        if b.held_view is not None:
            return None
        if b._scene is None:
            b._show()                                   # described once, at the press
        if not b._scene or b._waiting is not None:
            return None
        drawn = _ids(b._scene)
        for lay, _, _ in grab:
            item = b.placed_item(lay)
            if lay not in drawn or keys_of(item, "x") or keys_of(item, "y"):
                return None
        g = cls(b, grab)
        try:                                            # the release's own operations, checked now on this state
            run.plan_indexed(b.doc.kind, b.doc.data, g.calls(), idx=b.doc._index())
        except Exception:  # noqa: BLE001  refused: the per-move way says why, as before
            return None
        return g

    def _values(self) -> dict:
        ox, oy = self.at
        out = {}
        for lay, x0, y0 in self.grab:
            dx, dy = self.b._parent_drag(lay, ox, oy)
            out[lay] = (round(x0 + dx, 2), round(y0 + dy, 2))
        return out

    def calls(self) -> list:
        """The operations of the drag so far (applied once, at the release)."""
        b, out = self.b, []
        for lay, (x, y) in self._values().items():
            item = b.doc.item(lay)
            out += [route.value_call(item, "x", x, b.own_t(lay)), route.value_call(item, "y", y, b.own_t(lay))]
        return out

    def move(self, ox, oy):
        """The drag is (ox, oy) from its start: the engine draws the layers there; the outlines follow that picture."""
        self.at, self.moved = (ox, oy), True
        self.draw()

    def draw(self):
        """The picture at the drag's place now: every move, and any redraw asked meanwhile (bridge2d._show: a sharper
        picture once the drag rests, the view moved), which would otherwise draw the layers back where they were."""
        b, values = self.b, self._values()
        edits = [{"id": lay, "props": {"x": x, "y": y}} for lay, (x, y) in values.items()]
        tag = (_moved(b.doc.data, b.doc.locs(), b.doc.kind.lists, values), b.marks.times if b.marks else None, b._t)
        b.frames.request_edit(b._scene, edits, b._t, b.play.samples(), b.frame_scale(), tag, **b.frame_extras())


def _ids(node) -> set:
    """Every node id in a scene description."""
    out, stack = set(), [node]
    while stack:
        n = stack.pop()
        if isinstance(n, dict):
            if "id" in n:
                out.add(n["id"])
            stack.extend(v for v in n.values() if isinstance(v, (list, dict)))
        elif isinstance(n, list):
            stack.extend(n)
    return out


def _moved(data: dict, locs: dict, lists: dict, values: dict) -> dict:
    """The document with those layers' x, y: a copy of only the way down to them (the rest shared, never changed)."""
    way = set()
    for i in values:
        p = locs[i].parent
        while p is not None and p not in way:
            way.add(p)
            p = locs[p].parent

    def copy(node):
        new = dict(node)
        if node.get("id") in values:
            new["x"], new["y"] = values[node["id"]]
        if node.get("id") in way:
            for key in child_keys(node, lists) or ("comps",):
                if key in node:
                    new[key] = [copy(c) if c.get("id") in way or c.get("id") in values else c for c in node[key]]
        return new
    return copy(data)
