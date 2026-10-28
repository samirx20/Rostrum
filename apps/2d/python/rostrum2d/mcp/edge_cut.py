"""A subject cut by the frame edge: a layer, group or rig (a character's whole posed body) whose box crosses an edge of the
picture by a meaningful share while most of it is in the picture. From boxes, no drawing. Not flagged: what is fully in or out,
what spans the picture on either axis (a background, a wall, a ground strip: none of its edges), and bleeds under CUT_MIN_PCT. Facts with times, never a
verdict: a crop can be meant, the agent decides (guide: character-rigging-and-lip-sync.md › Staging a character)."""
from __future__ import annotations

from rostrum2d.frame import view

from . import world_facts as wf
from .geometry import _apply, _invert, comp_size

MOST_IN_PCT = 50          # at least this share of the box is in the picture
SOME_IN_PCT = 5           # a character is named when at least this share of it is in the picture
CUT_MIN_PCT = 8           # an edge counts when this share of the box's size lies beyond it
SOFT_BLUR = 20            # a layer blurred this much or more is atmosphere (a glow, a colour blob), never a cut subject
PARTS = ("shape", "text", "image", "video", "drawing", "path")      # what a rig's posed body is made of


def cut_edges(box: tuple[float, float, float, float], width: float, height: float, character: bool = False) -> dict[str, float]:
    """{edge: % of the box's size beyond that edge} for a box (left, top, right, bottom) in picture px that is mostly in.
    `character` (a rig's posed body): named however little is in (a face filling the picture cuts the body on every side), and a body
    that spans the picture is a crop, not a bleed."""
    l, t, r, b = box
    bw, bh = r - l, b - t
    if bw <= 0 or bh <= 0:
        return {}
    inside = max(0.0, min(r, width) - max(l, 0)) * max(0.0, min(b, height) - max(t, 0)) / (bw * bh)
    if inside * 100 < (SOME_IN_PCT if character else MOST_IN_PCT):
        return {}
    if not character and ((l <= 0 and r >= width) or (t <= 0 and b >= height)):
        return {}       # spans the picture on an axis: a backdrop, wall, sky or ground strip, its other edges bleed on purpose too
    out = {"left": max(0.0, -l) / bw, "right": max(0.0, r - width) / bw, "top": max(0.0, -t) / bh, "bottom": max(0.0, b - height) / bh}
    return {e: round(100 * v) for e, v in out.items() if v * 100 >= CUT_MIN_PCT}


def rig_parts(comp: dict) -> dict[str, list[str]]:
    """{rig id: the ids of the painted parts inside it}, every rig of the composition."""
    found, todo = {}, list(comp.get("layers", []))
    while todo:
        layer = todo.pop()
        if layer.get("type") == "rig":
            ids, stack = [], list(layer.get("layers", []))
            while stack:
                c = stack.pop()
                stack.extend(c.get("layers", []))
                if c.get("type") in PARTS:
                    ids.append(c["id"])
            found[layer["id"]] = ids
        todo.extend(layer.get("layers", []))
    return found


def ask_drawn(ask, t: float, ids: list[str]) -> dict:
    """The engine's placements of `ids` at t, leaving out parts not drawn then (a swapped-out mouth or eye fails a whole
    ask, so a failed ask is retried part by part)."""
    try:
        return ask(t, ids) if ids else {}
    except Exception:       # noqa: BLE001  (one undrawn part fails the whole ask)
        places = {}
        for i in ids:
            try:
                places.update(ask(t, [i]))
            except Exception:       # noqa: BLE001  (not drawn at t: simply not measured)
                pass
        return places


def rig_boxes(doc_data: dict, comp: dict, times: list[float]) -> tuple[list[dict[str, tuple]], list[str]]:
    """Per time {rig id: its posed body's box in picture px} (the engine poses it: placement.asker), and notes for rigs not measured."""
    from rostrum2d import placement
    rigs = {k: v for k, v in rig_parts(comp).items() if v}
    if not rigs or not times:
        return [{} for _ in times], []
    ask = placement.asker(doc_data, comp["id"], (min(times), max(times)))
    w, h = comp_size(comp)
    out, notes = [], []
    for t in times:
        inv = _invert(view.world_matrix(comp, view.shot(comp, t), {"screenLock": True}))
        row = {}
        for rid, ids in rigs.items():
            places = ask_drawn(ask, t, ids)
            if not places:
                note = f'rig "{rid}" could not be measured for the edge check: no part is drawn at {t:g} s'
                if note not in notes:
                    notes.append(note)
                continue
            pts = [_apply(inv, *placement.comp_point(p, x, y)) for p in places.values() if p.get("w") and p.get("h")
                   for x, y in ((0, 0), (p["w"], 0), (p["w"], p["h"]), (0, p["h"]))]
            if inv and pts:
                row[rid] = wf.bounds(pts)
        out.append(row)
    return out, notes


def soft(layer: dict) -> bool:
    """A layer blurred by SOFT_BLUR px or more: a glow or a colour blob of the atmosphere, with no edge a crop could cut."""
    return any(e.get("type") == "blur" and float(e.get("radius", 0)) >= SOFT_BLUR for e in layer.get("effects", []))


def subjects_at(comp: dict, t: float, rigs: dict[str, tuple]) -> list[tuple[str, str, tuple]]:
    """(id, type, box in picture px) of every showing top-level layer at t (not a soft blurred one), and each rig's posed
    body (replacing the rig layer's own box)."""
    blurred = {layer["id"] for layer in comp.get("layers", []) if soft(layer)}
    rows = [(r["id"], r["type"], tuple(r["box"][k] for k in ("left", "top", "right", "bottom")))
            for r in wf.in_frame(comp, t) if r["showing"] and r["id"] not in rigs and r["type"] != "rig" and r["id"] not in blurred]
    return rows + [(rid, "rig", box) for rid, box in rigs.items()]


def scan(comp: dict, times: list[float], rigs: list[dict[str, tuple]], step: float) -> list[dict]:
    """Stretches where a subject is cut by an edge: {id, type, edge, cut_pct (the most in the stretch), start, end}, in time order."""
    w, h = comp_size(comp)
    open_, done = {}, []
    for t, rig_row in zip(times, rigs):
        now = {}
        for sid, kind, box in subjects_at(comp, t, rig_row):
            for edge, pct in cut_edges(box, w, h, kind == "rig").items():
                now[(sid, edge)] = (kind, pct)
        for key in list(open_):
            if key not in now:
                done.append(open_.pop(key))
        for key, (kind, pct) in now.items():
            row = open_.setdefault(key, {"id": key[0], "type": kind, "edge": key[1], "cut_pct": 0, "start": t, "end": t})
            row["cut_pct"], row["end"] = max(row["cut_pct"], pct), t
    done += open_.values()
    for r in done:
        r["end"] = round(r["end"] + step, 3)
        r["start"] = round(r["start"], 3)
    return sorted(done, key=lambda r: (r["start"], r["id"], r["edge"]))


def tell(rows: list[dict], limit: int = 4) -> str:
    """The short sentence for a reply ('' when nothing is cut)."""
    if not rows:
        return ""
    shown = "; ".join(f'{r["id"]} ({r["type"]}) cut at the {r["edge"]} edge, up to {r["cut_pct"]} % of it outside, ' + (f'at {r["start"]:g} s' if r["start"] == r["end"] else f'{r["start"]:g}–{r["end"]:g} s')
                      for r in rows[:limit]) + (f"; and {len(rows) - limit} more" if len(rows) > limit else "")
    return f"Cut by the frame edge: {shown}. A crop meant as a close shot is yours to keep; a body or prop cut by accident is not (look_in_frame has the boxes)."


def warnings_at(doc_data: dict, comp: dict, t: float) -> list[str]:
    """The reply warnings for one frame (look_frame): what is cut by an edge at t, and any rig that could not be measured."""
    rigs, notes = rig_boxes(doc_data, comp, [t])
    return [s for s in (tell(scan(comp, [t], rigs, 0.0)),) if s] + notes
