"""What look_frame says about its picture besides the picture (SPEC §7, Lull 5, 6, 15): how much of it is blown out, and
which lighting settings only the Final look (Cycles) applies, so an agent reading a quick look knows what it isn't seeing.
"""
from __future__ import annotations

from pathlib import Path

CLIP = 254                       # an 8-bit channel at or above this is clipped (white, no detail left)


def clipped_percent(png: str | Path) -> float:
    """The share of pixels with any colour channel clipped, in percent."""
    import numpy as np
    from PIL import Image
    with Image.open(png) as im:
        px = np.asarray(im.convert("RGB"))
    return round(100.0 * float((px >= CLIP).any(axis=2).mean()), 2)


def final_only(scene: dict) -> list[str]:
    """'spread on rim', 'linking on rim': lighting settings in this scene that only Final (Cycles) applies."""
    out, stack = [], list(scene.get("items", []))
    while stack:
        node = stack.pop(0)
        p = node.get("props", {})
        if node.get("type") == "light":
            if p.get("kind") in ("rect", "disk", "strip") and p.get("spread", 180.0) < 180.0:
                out.append(f'spread on {node["id"]}')
            if p.get("lightsOnly"):
                out.append(f'linking on {node["id"]}')
        stack += node.get("children", [])
    return out


def line(png, scene: dict, renderer: str) -> tuple[str, dict]:
    """(' Clipped: 3 % of pixels. Applied in Final: …', facts) for the reply."""
    pct, final = clipped_percent(png), final_only(scene)
    text = f" Clipped: {pct:g} % of pixels" + (" (blown out: lower Exposure)" if pct >= 2 else "") + "."
    if final:
        text += (" Applied in Final: " if renderer != "cycles" else " Applied here (Final only): ") + ", ".join(final) + "."
    return text, {"clippedPercent": pct, "appliedInFinal": final}



def copies_line(copies: dict, names: dict) -> tuple[str, dict]:
    """(' Copies: buds 212 of 400 seen by Hero 01; rocks 60.', facts) from the engine's scene reply (`copies`: {id: {count, seen,
    camera}}); `names`: item id -> the name a person sees. Nothing said when the scene has no copies."""
    parts = []
    for id_, c in sorted(copies.items()):
        who = names.get(id_, id_)
        if c.get("seen") is None:
            parts.append(f"{who} {c['count']}")
        else:
            parts.append(f"{who} {c['seen']} of {c['count']} seen by {names.get(c.get('camera'), c.get('camera'))}")
    return (f" Copies: {'; '.join(parts)}." if parts else ""), ({"copies": copies} if copies else {})


def item_names(items: list[dict]) -> dict:
    """Item id -> name over a document's item tree."""
    out, stack = {}, list(items)
    while stack:
        it = stack.pop()
        out[it["id"]] = it.get("name") or it["id"]
        stack += it.get("children", [])
    return out
