"""Paint layers shared by every drawing of a layer (painting spec §2.3.6; the kit's linked.py): a drawing layer's or a
painted element's drawings all hold the same paint layers (Ink over Colour on every drawing), each with its own
strokes. Which drawings share (`peers`), a blank drawing with the layer's paint layers (`blank_frame`), adding a
paint layer to all (`add`), the document check (`problems`) and an older file's drawings lined up on open (`upgrade`).
"""
from __future__ import annotations

import copy

from rostrum_core.tree import index, walk
from rostrum_paint import linked
from rostrum_paint.ops import build


def peers(ctx, canvas_id: str) -> list[str]:
    """The drawings sharing paint layers with this one: every drawing of its layer, itself included."""
    return [f["id"] for f in ctx.item(ctx.idx[canvas_id].parent).get("frames", [])]


def blank_frame(ctx, holder: dict, at: int, id_: str | None = None) -> dict:
    """A new empty drawing for `holder`: its paint layers (empty), or one "Ink" layer for the first drawing."""
    frame = {"id": id_ or ctx.new_id("frame"), "type": "frame", "at": at, "paints": [], "paintmasks": []}
    frames = holder.get("frames", [])
    taken = set(index(ctx.doc, ctx.kind.lists)) | {frame["id"]}
    for p in (frames[0]["paints"] if frames else [build("paint", "", {"name": "Ink"})]):
        n = 1
        while f"paint_{n}" in taken:
            n += 1
        taken.add(f"paint_{n}")
        frame["paints"].append(linked.blank(p, f"paint_{n}") if frames else {**p, "id": f"paint_{n}"})
    return frame


def add(ctx, frame_id: str, paint: dict, index_=None):
    """A new paint layer on a drawing and, empty, on every other drawing of its layer (one change)."""
    linked.add(ctx, frame_id, paint, index_, peers)


def problems(item: dict) -> list[str]:
    return linked.problems(item["id"], item.get("frames", []))


def upgrade(data: dict, lists: dict):
    """(new data, label) with each layer's drawings sharing paint layers, or None when they already do. The first
    drawing's paint layers become the layer's; another drawing's joins the first unused one of the same name (taking
    its settings), or is added to every drawing (empty elsewhere). What changed is said in the label."""
    if not any(problems(i) for i in walk(data, lists) if len(i.get("frames", [])) > 1):
        return None
    work = copy.deepcopy(data)
    ids = set(index(work, lists))
    notes = []
    for item in walk(work, lists):
        if len(item.get("frames", [])) > 1 and problems(item):
            notes += _align(item, ids)
    return work, "Paint layers shared across drawings" + (f" ({'; '.join(notes[:4])})" if notes else "")


def _align(item: dict, ids: set) -> list[str]:
    frames, notes = item["frames"], []
    layers = [copy.deepcopy(p) for p in frames[0]["paints"]]           # the layer's paint layers, bottom first
    mine = []                                                           # per drawing: key -> its paint layer
    for f in frames:
        got = {}
        for p in f["paints"]:
            k = linked.key(p)
            match = next((q for q in layers if linked.key(q) == k and k not in got), None) or \
                next((q for q in layers if q.get("name") == p.get("name") and linked.key(q) not in got), None)
            if match is None:
                layers.append(p)
                match = p
                if f is not frames[0]:
                    notes.append(f'{f["id"]}\'s "{p.get("name")}" added to every drawing')
            elif any(p.get(s) != match.get(s) for s in linked.SHARED):
                notes.append(f'{f["id"]}\'s "{p.get("name")}" took the first drawing\'s settings')
            got[linked.key(match)] = p
        mine.append(got)
    for f, got in zip(frames, mine):
        out = []
        for q in layers:
            p = got.get(linked.key(q))
            if p is None:
                n = 1
                while f"paint_{n}" in ids:
                    n += 1
                ids.add(f"paint_{n}")
                p = linked.blank(q, f"paint_{n}")
            else:
                p.update({s: q[s] for s in linked.SHARED if s in q})
                if p is not q and linked.key(q) != p["id"]:
                    p["layer"] = linked.key(q)
            out.append(p)
        f["paints"] = out
    return notes
