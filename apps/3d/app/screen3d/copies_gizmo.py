"""The gizmo on one copy (brief 24): click a copy (copies_qt.picked) and the handles stand on it. A drag moves, turns or
sizes that copy live (a `copies` request with `held`, copies_live.py: no new scene) and the drop is one `copies.hold`
(one undo step; a held copy never moves when the layout changes). Esc puts it back. A mix-in for gizmo_qt.Gizmo; the
maths is gizmo.py's and gizmo_drag.py's, as for any item: the copy's place is the item's own x y z rx ry rz, its size
is all three scales, and its carrier is the copies item's world. A keyed copy (Turn into keys on falling copies,
copy_keys.py): the handles stand where it is at the playhead, the other keyed copies keep moving during the drag, and the
drop keys the moved fields at this frame (`copies.key`, with `copies.hold` for the rest, one undo step).
"""
from __future__ import annotations

from PySide6.QtGui import QGuiApplication
import math

from rostrum3d import aim, copies_fields as CF, copy_keys as CK, through
from rostrum_gui.snap import Target

from . import gizmo as G
from .copies_actions import HOLD

KEY = "copies.key"
from .copies_live import Live
from .gizmo_drag import MOVE, TURN, SCALE, item_drag

HELD = ("x", "y", "z", "rx", "ry", "rz", "s")


class HeldLive(Live):
    """The live sender of a copy drag: send(item, row) puts the held row on the stage (newest wins, as every drag). The
    request's `held` is the whole list (contract v1.21), so the copies held already go along."""

    def __init__(self, link, refused, others):
        super().__init__(link, refused)
        self.others = others

    def send(self, item, row):
        super().send(item, held=[*(r for r in self.others if r["copy"] != row["copy"]), row])


def held_rows(item: dict) -> list[dict]:
    return [{"copy": i, **{k: float(v) for k, v in row.items()}} for i, row in CF.held_map(item).items()]


def _node(items: list, id_: str) -> dict | None:
    for n in items:
        if n["id"] == id_:
            return n
        if (got := _node(n.get("children", []), id_)) is not None:
            return got
    return None


def scene_held(scene: dict, item_id: str) -> list[dict]:
    """The copies item's `held` list as the compiled scene sends it: held copies and keyed ones with their `anim`
    (copy_keys.py), so a live request keeps the keyed copies moving."""
    node = _node(scene.get("items", []), item_id)
    return list(node.get("held", [])) if node else []


def keyed_now(scene: dict, item_id: str, index: int, frame: int) -> dict:
    """Copy `index`'s keyed values at `frame` ({} when it has no keys): where it is seen at the playhead, before effectors."""
    row = next((h for h in scene_held(scene, item_id) if h["copy"] == index and "anim" in h), None)
    if row is None:
        return {}
    k = frame - scene["shot"]["start"]
    return {p: float(vals[min(max(k, 0), len(vals) - 1)]) for p, vals in row["anim"].items()}


def layout_place(item: dict, i: int) -> dict | None:
    """Where copy `i` of a line, grid or circle stands (the copies item's space) when nothing varies it: what the pick
    reply's `place` would say. None for a surface or a varied layout (only the engine knows those places)."""
    if item.get("layout") == "surface" or any(item.get(k, 0) for k in ("varyMove", "varyTurn", "varyScale")):
        return None
    out = {"x": 0.0, "y": 0.0, "z": 0.0, "rx": 0.0, "ry": 0.0, "rz": 0.0, "s": 1.0}
    if item["layout"] == "line":
        out.update(x=i * item.get("spacingX", 0.0), y=i * item.get("spacingY", 0.0), z=i * item.get("spacingZ", 0.0))
    elif item["layout"] == "grid":
        cols = max(1, int(item.get("columns", 4)))
        out.update(x=(i % cols) * item.get("spacingX", 0.0), z=(i // cols) * item.get("spacingZ", 0.0))
    else:
        a = 2 * math.pi * i / max(1, int(item["count"]))
        out.update(x=item["radius"] * math.sin(a), z=item["radius"] * math.cos(a), ry=math.degrees(a) if item.get("faceOut", True) else 0.0)
    return out


def row_of(index: int, values: dict) -> dict:
    return {"copy": index, **{k: float(values[k]) for k in HELD}}


class CopyGizmo:
    def _copy_setup(self, it):
        """The gizmo's context for the picked copy of `it`, in gizmo_qt._setup's shape; None when its place is unknown."""
        tool, vp = self.vp.copies, self.vp
        place = tool.place()
        if place is None:
            return None
        scene, cam = vp.sent()
        w, h = vp._size
        view = G.View.of(cam, scene, self.bridge.frame, w, h)
        carrier = through.find_item(scene, it["id"], self.bridge.frame)[0]
        v = {**{k: 0.0 for k in (*MOVE, *TURN, "px", "py", "pz")}, **{k: float(place.get(k, 0.0)) for k in HELD[:6]},
             "sx": float(place.get("s", 1.0)), "sy": float(place.get("s", 1.0)), "sz": float(place.get("s", 1.0)),
             "aim": "none"}
        pw, origin, turn = G.item_frame(carrier, v)
        screen = QGuiApplication.primaryScreen()
        px = vp._scale * (screen.devicePixelRatio() if screen else 1.0)
        return {"it": it, "v": v, "view": view, "pw": pw, "origin": origin, "turn": turn, "axes": G.columns(pw[0]),
                "own": G.columns(aim._mul(pw[0], turn)), "px": px, "scene": scene, "parent": it["id"], "mesh": False,
                "copy": tool.copy["index"]}

    def _copy_live(self):
        """The live sender: the other copies go along as the scene has them (keyed ones keep moving); the dragged one is
        sent still, where the pointer puts it."""
        from .copies_live import available
        others = scene_held(self.vp.sent()[0], self.bridge.selected)
        return HeldLive(self.vp.link, self._unlive, others) if available(self.bridge) else None

    def _copy_calls(self, c, row) -> list[dict]:
        """The drop's change: a keyed copy's keyed fields get a key at this frame (copies.key: it ends where it was
        dropped, here); the rest of a move, and any size change, holds the copy (copies.hold). [] when nothing moved."""
        was = {**{k: c["v"][k] for k in (*MOVE, *TURN)}, "s": c["v"]["sx"]}
        moved = [k for k in row if abs(row[k] - was[k]) >= 1e-9]
        keyed = {p for p, ks in CK.keys_map(c["it"]).get(c["copy"], {}).items() if ks}
        scene = self.vp.sent()[0]
        t = round(self.bridge.frame / scene["shot"]["fps"], 4)
        id_ = c["it"]["id"]
        calls = [{"op": KEY, "target": [id_], "args": {"copy": c["copy"], "prop": k, "t": t, "v": row[k]}}
                 for k in moved if k in keyed]
        if any(k not in keyed for k in moved):
            calls.append({"op": HOLD, "target": [id_], "args": {"copy": c["copy"], **row}})
        return calls

    def _copy_drag(self, g, c, now, free):
        """One move of the copy: the new place goes to the view; the drop's `copies.hold` is the call kept."""
        out, self._label = item_drag(g, c, now, free, lambda _c, _k: [Target("edge", "0", 0.0)])
        v = dict(c["v"])
        for k in (*MOVE, *TURN):
            if k in out:
                v[k] = out[k]
        for k in SCALE:                              # a copy is sized as one: whichever scale handle moved sets all three
            if k in out:
                v["sx"] = v["sy"] = v["sz"] = out[k]
        row = {**{k: v[k] for k in (*MOVE, *TURN)}, "s": v["sx"]}
        g["calls"] = self._copy_calls(c, row)
        same = not g["calls"]
        if self._live is None:
            self.bridge._guard(lambda: self._drag.preview(g["calls"]))
            self.changed.emit()
        elif not same:
            self._live.send(c["it"]["id"], row_of(c["copy"], row))
            pw, origin, turn = G.item_frame(c["pw"], {**v, "sx": v["sx"]})
            self._ctx = {**c, "origin": origin, "turn": turn, "own": G.columns(aim._mul(pw[0], turn))}
            self._place()

    def _copy_put_back(self, sender):
        """After a live copy drag that changed nothing: the copy on the stage goes back to where it was held."""
        if sender is None or not sender.sent:
            return
        c = self._grab["ctx"]
        was = next((h for h in sender.others if h["copy"] == c["copy"]), None)    # a keyed copy: its keys back too
        sender.send(c["it"]["id"], was or row_of(c["copy"], {**c["v"], "s": c["v"]["sx"]}))
