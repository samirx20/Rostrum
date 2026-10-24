"""Send a shot to 2D (SPEC §12): the shot's render of the scene as it is now, placed in a chosen 2D scene as a 3D render
layer (2D's `render3d`), live-linked: it follows that shot's newest render, and 2D says "out of date" when the 3D
document's content no longer matches the render's `scene_hash` (rostrum2d/render3d.py).

The link is made in the 2D document through 2D's own operations (`layer.add`, `render3d.set`), on the document opened
live (rostrum_core.live.keep: lock, catch up, change, save), so it is one step in 2D's history by whoever sent it, and an
open 2D window sees it arrive. Sending again finds the same layer (same 3D item and shot in that scene) and only sets it
to follow the newest render: what a person moved, sized or timed in 2D stays (AGENTS.md rule 3).

The Editor is not built yet: sending to it fails loudly (`target="editor"`). No Qt.
"""
from __future__ import annotations

from rostrum_core import Document, RostrumError, codes, ids, live, project
from rostrum_core.storage import doc_hash
from rostrum_core.tree import index

TARGETS = ("2d", "editor")


class NeedsRender(RostrumError):
    """The shot has no finished render (with EXR frames) of the 3D document as it is now: render it, then send."""


def _kind2d():
    try:
        from rostrum2d import KIND
    except ImportError as e:
        raise RostrumError(codes.NOT_FOUND, "shot.send", "Rostrum2D", "is not installed here, so there is no 2D document to send to") from e
    return KIND


def _source(r: dict) -> dict:
    return r["manifest"].get("source", {})


def current_render(folder, item_id: str, shot_id: str, data: dict) -> dict | None:
    """The shot's newest render with EXR frames whose scene hash is the document's now; None when it has none."""
    now = doc_hash(data)
    for r in project.renders(folder, item_id):
        s = _source(r)
        if (r["kind"] == "pictures" and s.get("shot") == shot_id and (s.get("scene_hash") or s.get("doc_hash")) == now
                and any(f.lower().endswith(".exr") for f in r["files"])):
            return r
    return None


def _layers(holder: dict):
    for it in holder.get("layers", []):
        yield it
        yield from _layers(it)


def _linked(comp: dict, item_id: str, shot_id: str) -> dict | None:
    return next((l for l in _layers(comp) if l["type"] == "render3d" and l.get("item") == item_id and l.get("shot", "") == shot_id), None)


def scenes(folder) -> list[dict]:
    """Every 2D scene of the project: {value "<2D item>/<scene id>", item, comp, label}. Read only."""
    out, kind = [], _kind2d()
    for it in project.items(folder, "2d"):
        doc = Document.open(folder, it["id"], kind)
        for c in doc.data.get("comps", []):
            label = c.get("name") or c["id"]
            out.append({"value": f'{it["id"]}/{c["id"]}', "item": it["id"], "comp": c["id"], "label": label, "in": it["name"]})
    return out


def pick(folder, item_id: str, shot_id: str, scene: str | None) -> dict:
    """The 2D scene asked for ("<item>/<scene>" or a scene id), else the one the shot was sent to before, else the only one."""
    found = scenes(folder)
    if not found:
        raise RostrumError(codes.NOT_FOUND, "shot.send", "a 2D scene", "this project has no 2D item to send to",
                           hint="Make a 2D item in the project first (Rostrum2D).")
    if scene:
        hit = [s for s in found if scene in (s["value"], s["comp"])]
        if len(hit) == 1:
            return hit[0]
        raise RostrumError.not_found("shot.send", "2D scene", scene, [s["value"] for s in found], "this project")
    kind = _kind2d()
    before = [s for s in found if _linked(Document.open(folder, s["item"], kind).item(s["comp"]), item_id, shot_id)]
    if len(found) == 1 or len(before) == 1:
        return (before or found)[0]
    raise RostrumError(codes.BAD_ARGUMENT, "shot.send", "scene", f"is needed: the project has {len(found)} 2D scenes",
                       [s["value"] for s in found], "Pick the 2D scene to send to.")


def link_2d(folder, item_id: str, shot: dict, scene: dict, who) -> dict:
    """Put (or keep) the shot's 3D render layer in the 2D scene, as one 2D step by `who`. {item, comp, layer, made, changed}"""
    doc = Document.open(folder, scene["item"], _kind2d())
    live.keep(doc)
    comp = doc.item(scene["comp"])
    old, label = _linked(comp, item_id, shot["id"]), f'Send {shot.get("name") or shot["id"]} from Rostrum3D'
    if old is not None:
        lid = old["id"]
        calls = [{"op": "render3d.set", "target": [lid], "args": {"version": 0}}] if old.get("version", 0) else []
    else:
        lid = ids.counted(set(index(doc.data, doc.kind.lists)), "render3d")
        w, h = int(comp.get("width", 1920)), int(comp.get("height", 1080))
        calls = [{"op": "layer.add", "target": [comp["id"]], "args": {"type": "render3d", "id": lid, "name": f'3D · {shot.get("name") or shot["id"]}'}},
                 {"op": "render3d.set", "target": [lid], "args": {"item": item_id, "shot": shot["id"], "version": 0, "w": w, "h": h,
                                                                  "x": w / 2, "y": h / 2}}]
    changed = doc.apply(calls, who, label) if calls else None
    if changed is not None:
        doc.save()                                # the document file too, for readers of the file alone
    return {"target": "2d", "item": scene["item"], "comp": scene["comp"], "scene": scene["label"], "layer": lid,
            "made": old is None, "changed": changed is not None}


def send_shot(folder, doc3d, shot_id: str, target: str = "2d", scene: str | None = None, who=None) -> dict:
    """Link the shot's current render into the target. {link, render: {version, path}}. Raises NeedsRender when the shot
    has no render of the document as it is now (render it with EXR frames first), loud for everything else."""
    from rostrum_core.who import Who
    if target not in TARGETS:
        raise RostrumError(codes.BAD_ARGUMENT, "shot.send", f'target "{target}"', "is not a place to send to", list(TARGETS))
    if target == "editor":
        raise RostrumError(codes.NOT_FOUND, "shot.send", "the Editor", "isn't built yet, so a shot can't be sent to it",
                           hint="Send it to 2D, or render it with EXR frames (render_video exr: true); the Editor will read those.")
    if not folder or not doc3d.item_id:
        raise RostrumError(codes.BAD_ARGUMENT, "shot.send", "the 3D document", "is not saved in a project folder, so 2D can't see it")
    shot = next((s for s in doc3d.data.get("shots", []) if s["id"] == shot_id), None)
    if shot is None:
        raise RostrumError.not_found("shot.send", "shot", shot_id, [s["id"] for s in doc3d.data.get("shots", [])])
    where = pick(folder, doc3d.item_id, shot_id, scene)          # before the render check: a wrong scene says so first
    r = current_render(folder, doc3d.item_id, shot_id, doc3d.data)
    if r is None:
        raise NeedsRender(codes.NOT_FOUND, "shot.send", f'shot "{shot_id}"', "has no render of the scene as it is now (with EXR frames)",
                          hint="Render it first (Render page, or render_video exr: true), then send; the render_send_shot tool renders it first by itself.")
    link = link_2d(folder, doc3d.item_id, shot, where, who or Who.agent("rostrum-3d"))
    return {"link": link, "render": {"version": r["version"], "path": r["path"], "scene_hash": _source(r).get("scene_hash") or _source(r).get("doc_hash")}}
