"""The frame's actions (camera spec § 3.4, 4.5, 4.6, 6): with the frame picked the actions row shows Frame the view ·
Cut here · ⋯ (Frame home, Lock); with layers picked ⋯ holds Frame these and Cut to these; Ctrl+K also has Cut to the
view, and Frame the view / Cut to the view with nothing picked. Each is one change through `frame.fit`, `frame.cut` or
`frame.home` on the frame, the operations an agent calls too.

Plain data read by actions.py (`data`), facts read by action_rules.Facts (`facts`, from the screen's `state`), the calls
rule `{"rule": "frame", "how": …}` (`calls`) and the status line after the change (`told`). No Qt.

`at` is the playhead in the frame's own seconds; on a marker it is the marker ("#logo lands"), so the key or the cut is
tied to it and moves with it (spec § 5 #20). "The view" is the world rectangle the canvas shows (world_view.visible),
less the room Fit the frame keeps round the frame: after Frame the view, the frame sits where Ctrl+0 would show it.
"""
from __future__ import annotations

from rostrum2d.frame import fit as frame_fit, view as frame_view
from rostrum2d.ops_frame_fit import words

GROUP = "frame"                     # its own block on right-click (action_slots.actionMenu), first
OPS = ("frame.fit", "frame.cut", "frame.home")
WHY = ("The frame moves only while it is unlocked and not riding a path; a cut needs the playhead after 0 s, Frame home "
       "a frame away from home. Pick the frame with C.")
WHY_THESE = "Pick unlocked layers (not the frame), with the frame unlocked; a cut needs the playhead after 0 s."
ROOM = 24.0                         # screen px kept round the framed view: the fit's room (CanvasView.qml frameMargin)


def state(b) -> dict:
    """What the frame actions read from the screen: the frame's id, the playhead (its own seconds), the marker under
    the playhead (""), the view's world rect (None before the canvas is laid out), whether it is home, and whether it is
    held (locked, or riding a path: its place comes from the path, so framing it is not offered)."""
    comp = b.comp()
    fr = frame_view.of(comp)
    if fr is None:
        return {}
    t, fps = b.own_t(fr["id"]), float(comp.get("fps", 30)) or 30.0
    marker = next((n for n, s in sorted(b.times().items()) if abs(s - b._t) < 0.5 / fps), "")
    shot = frame_view.shot(b.placed(), b._t)         # keys on a marker placed (the frame's own time is the scene's)
    home = shot is None or (abs(shot.x - shot.hx) < 0.01 and abs(shot.y - shot.hy) < 0.01
                            and abs(shot.zoom - 1.0) < 1e-4 and abs(shot.roll) < 1e-3)
    view = _inside(b._world.visible(), b.view_zoom())
    return {"id": fr["id"], "t": round(t, 4), "marker": marker, "view": view,
            "held": bool(fr.get("locked") or fr.get("ridePath")), "home": home, "framed": _framed(shot, view, comp)}


def _framed(shot, view: dict | None, comp: dict) -> bool:
    """The frame already shows exactly the view: Frame the view would key what is there (the operation refuses it too)."""
    if shot is None or not view or view["w"] <= 0 or view["h"] <= 0:
        return False
    x, y, z = frame_fit.rect((view["x"], view["y"], view["w"], view["h"]), (float(comp.get("width", 1920)), float(comp.get("height", 1080))),
                             shot.roll, 0.0)
    return abs(x - shot.x) < 0.01 and abs(y - shot.y) < 0.01 and abs(z - shot.zoom) < 1e-4


def _inside(v: dict | None, zoom: float) -> dict | None:
    """The view less the fit's room on each side, so the framed frame shows whole, as Ctrl+0 would show it."""
    if v is None:
        return None
    m = ROOM / max(zoom, 1e-6)
    return {"x": v["x"] + m, "y": v["y"] + m, "w": v["w"] - 2 * m, "h": v["h"] - 2 * m}


def facts(f) -> dict:
    """The facts the frame actions' `when` reads (action_rules.Facts adds them)."""
    s = f.state.get("frame") or {}
    view = s.get("view")
    return {"frame_alone": bool(s) and f.ids == [s["id"]], "frame_free": bool(s) and not s["held"],
            "frame_away": bool(s) and not s["home"], "after_start": s.get("t", 0.0) > 1e-6,
            "view_known": bool(view) and view["w"] > 0 and view["h"] > 0, "nothing_picked": not f.ids}


def _at(s: dict):
    return "#" + s["marker"] if s["marker"] else s["t"]


def calls(f, how: str) -> list[dict]:
    """how: view | items | home | cut | cut_view | cut_items — the one call on the frame ([] = nothing to do)."""
    s = f.state.get("frame") or {}
    if not s:
        return []
    if how == "home":
        return [{"op": "frame.home", "target": [s["id"]], "args": {"at": _at(s)}}]
    to = {}
    if how.endswith("view"):
        if not s.get("view"):
            return []
        to = {"to": "view", "rect": [round(s["view"][k], 2) for k in ("x", "y", "w", "h")]}
    elif how.endswith("items"):
        to = {"to": "items", "ids": list(f.ids)}
    op = "frame.cut" if how.startswith("cut") else "frame.fit"
    return [{"op": op, "target": [s["id"]], "args": {"at": _at(s), **to}}]


def data(a, R) -> list[dict]:
    """The entries, made with actions._a; `R(how)` is the calls spec."""
    alone = lambda *more: {"all": [{"fact": n} for n in ("frame_alone", "frame_free", *more)]}   # noqa: E731
    none = lambda *more: {"all": [{"fact": n} for n in ("nothing_picked", "frame_free", *more)]}  # noqa: E731
    free = lambda *more: {"all": [{"fact": n} for n in ("frame_free", *more)]}                    # noqa: E731
    one = {"group": GROUP, "frame_ok": True, "max_targets": 1, "why": WHY}
    nothing = {"group": GROUP, "panel": False, "min_targets": 0, "max_targets": 0, "why": WHY}
    return [
        a("frame_view", "Frame the view", rank=1, importance="primary", when=alone("view_known"), calls=R("view"), **one),
        a("cut_here", "Cut here", rank=2, importance="primary", when=alone("after_start"), calls=R("cut"), **one),
        a("frame_home", "Frame home", rank=3, when=alone("frame_away"), calls=R("home"), **one),
        a("cut_view", "Cut to the view", rank=4, when=alone("after_start", "view_known"), calls=R("cut_view"), panel=False, **one),
        a("frame_these", "Frame these", rank=3, group=GROUP, when=free(), calls=R("items"), why=WHY_THESE),
        a("cut_these", "Cut to these", rank=4, group=GROUP, when=free("after_start"), calls=R("cut_items"), why=WHY_THESE),
        a("frame_view_any", "Frame the view", rank=1, when=none("view_known"), calls=R("view"), **nothing),
        a("cut_view_any", "Cut to the view", rank=4, when=none("after_start", "view_known"), calls=R("cut_view"), **nothing),
    ]


def menu_rows(entries: list[dict]) -> list[dict]:
    """Right-click's frame block (spec § 3.4: on the Frame row and the canvas): the frame actions the panel shows."""
    return [{"value": e["id"], "label": e["label"], "keys": e["keys"], "group": GROUP, "sub": []}
            for e in entries if e["group"] == GROUP and e.get("panel", True)]


def already(calls: list[dict], f) -> bool:
    """The calls are Frame the view on a view the frame already shows: nothing to key (the status says so, no change is made)."""
    s = f.state.get("frame") or {}
    return bool(s.get("framed")) and any(c["op"] == "frame.fit" and c["args"].get("to") == "view" and not c["args"].get("cut") for c in calls)


def told(calls: list[dict], f) -> str:
    """What the status line says after the change, worked out BEFORE it (it says where the frame was): the operations'
    own words (ops_frame_fit.words); "" when the calls are not the frame's."""
    c = next((c for c in calls if c["op"] in OPS), None)
    s = f.state.get("frame") or {}
    return words(c["op"], f.doc.item(s["id"]), c["args"], s["t"]) if c and s else ""
