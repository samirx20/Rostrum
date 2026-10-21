"""The scene description: what the Python layer sends the engine (ENGINE_CONTRACT.md). One composition, every
item's still values with defaults filled in, and the keys of its animated fields; the engine evaluates them per
frame. `frame_at` is the same evaluation in Python (the reference, and the temporary evaluator's input).
"""
from __future__ import annotations

from . import fields as F
from .evaluate import animated, keys_of, resolve

FORMAT, VERSION = "rostrum-2d-scene", 1
KEY_FIELDS = ("t", "v", "c", "ease", "x1", "y1", "x2", "y2", "stiffness", "damping")


def _anim(item: dict) -> dict:
    return {prop: [{k: key[k] for k in KEY_FIELDS if k in key} for key in keys_of(item, prop)]
            for prop in sorted(animated(item))}


def _node(item: dict) -> dict:
    node = {"id": item["id"], "type": item["type"],
            "props": {p.name: item.get(p.name, p.default) for p in F.FIELDS[item["type"]]}}
    anim = _anim(item)
    if anim:
        node["anim"] = anim
    for key in ("effects", "masks", "layers"):
        if item.get(key):
            node[key] = [_node(child) for child in item[key]]
    return node


def describe(doc_data: dict, comp_id: str | None = None) -> dict:
    """The scene description of one composition (the first when not named)."""
    comps = doc_data.get("comps", [])
    if not comps:
        raise ValueError("the document has no composition yet (comp.add)")
    comp = comps[0] if comp_id is None else next((c for c in comps if c["id"] == comp_id), None)
    if comp is None:
        raise ValueError(f'no composition "{comp_id}"; there are: {", ".join(c["id"] for c in comps)}')
    return {"format": FORMAT, "version": VERSION, "comp": _node(comp)}


def frame_at(scene: dict, t: float) -> dict:
    """The scene at one time: every node's props evaluated, `anim` gone; nodes outside start..end dropped."""
    if scene.get("format") != FORMAT or scene.get("version") != VERSION:
        raise ValueError(f"not a {FORMAT} v{VERSION} scene: {scene.get('format')} v{scene.get('version')}")

    def at(node):
        item = {"id": node["id"], "type": node["type"], **node["props"],
                "keys": [{"prop": p, **k} for p, ks in node.get("anim", {}).items() for k in ks]}
        out = {"id": node["id"], "type": node["type"], "props": resolve(item, t)}
        for key in ("effects", "masks", "layers"):
            if key in node:
                kids = [at(c) for c in node[key]]
                out[key] = [k for k in kids if k is not None]
        props = out["props"]
        if node["type"] in F.LAYERS and not (props["start"] <= t < props["end"]):
            return None
        return out

    return {"format": FORMAT, "version": VERSION, "t": t, "comp": at(scene["comp"])}
