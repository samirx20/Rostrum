"""The scene description: what the Python layer sends the engine (ENGINE_CONTRACT.md). One composition, every
item's still values with defaults filled in, and the keys of its animated fields; the engine evaluates them per
frame (the evaluation's reference is evaluate.py).
"""
from __future__ import annotations

from . import drawing, fields as F, video
from .evaluate import animated, keys_of

FORMAT, VERSION = "rostrum-2d-scene", 1
KEY_FIELDS = ("t", "v", "c", "d", "ease", "x1", "y1", "x2", "y2", "stiffness", "damping")


def _anim(item: dict) -> dict:
    return {prop: [{k: key[k] for k in KEY_FIELDS if k in key} for key in keys_of(item, prop)]
            for prop in sorted(animated(item))}


def _node(item: dict, fps: float = 30) -> dict:
    node = {"id": item["id"], "type": item["type"],
            "props": {p.name: item.get(p.name, p.default) for p in F.FIELDS[item["type"]]}}
    anim = _anim(item)
    if anim:
        node["anim"] = anim
    for key in ("effects", "masks", "layers"):
        if item.get(key):
            node[key] = [_node(child, fps) for child in item[key]]
    if item["type"] == "rig":           # bones, iks and binds are nodes of their own (RIG.md § Scene description)
        node["rig"] = [_node(c, fps) for key in ("bones", "iks", "binds") for c in item.get(key, [])]
    if item["type"] == "drawing":       # the painting kit makes each drawing's picture once; the engine only reads it
        node["frames"] = [{"at": f["at"], "src": str(drawing.picture(item, f))} for f in item["frames"]]
    if item["type"] == "video":         # decoded once (video.py); the engine picks the frame by the time
        node["frames"] = video.frames({**node["props"], "id": item["id"]}, fps)
    return node


def describe(doc_data: dict, comp_id: str | None = None) -> dict:
    """The scene description of one composition (the first when not named)."""
    comps = doc_data.get("comps", [])
    if not comps:
        raise ValueError("the document has no composition yet (comp.add)")
    comp = comps[0] if comp_id is None else next((c for c in comps if c["id"] == comp_id), None)
    if comp is None:
        raise ValueError(f'no composition "{comp_id}"; there are: {", ".join(c["id"] for c in comps)}')
    return {"format": FORMAT, "version": VERSION, "comp": _node(comp, comp.get("fps", F.defaults("comp")["fps"]))}

