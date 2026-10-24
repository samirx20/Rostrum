"""A text whose font this computer lacks, on the canvas (the canvas never goes blank): the scene is drawn without it, and
in its place stands its own box with a dashed red edge and the font's name, from ordinary nodes, in the text's place
(the same pattern as scene.py's 3D placeholder). The box is the text's, measured in a font that surely exists.
Where a whole film is exported (scene.describe without a `span`) it is refused instead, naming the texts: a file is
never written with a stand-in in it. The Problems list says it in words (diagnose_engine.py) and `font.replace` fixes it.
"""
from __future__ import annotations

from . import fields as F, fontlist, textsize
from .engine import EngineError

RED = "#e5484d"


def trouble(item: dict) -> str | None:
    """The family this text names that the app and this computer lack (or whose italic it lacks), else None. No engine
    built: None (nothing can be drawn then, and the look tools say so)."""
    family = item.get("font", F.defaults("text")["font"])
    try:
        if family not in fontlist.names():
            return family
        fam = fontlist.family(family)
        return f"{family} (no italic)" if item.get("italic") and fam is not None and not fam["italic"] else None
    except (EngineError, OSError):
        return None


def refusal(missing: dict[str, str]) -> str:
    """Why a whole-film export is refused: {text id: the font's name}."""
    return "; ".join(f'{i}: {w}' for i, w in missing.items())


def stand_in(node: dict, label: str, engine_props) -> dict:
    """The text's node as a group at its place (its transform, timing and animation) holding a dashed red box and the
    font's name; `engine_props(type, given)`: scene.py's props filler."""
    w, h = textsize.size(node["props"])           # (measured in the stand-in font: textsize.key)
    w, h = max(w, 40.0), max(h, 24.0)
    group = engine_props("group", {**node["props"], "w": w, "h": h})
    anim = {k: v for k, v in node.get("anim", {}).items() if k in group}
    box = {"id": f'{node["id"]}.box', "type": "path", "props": engine_props("path", {
        "d": f"M0 0 L{w:g} 0 L{w:g} {h:g} L0 {h:g} Z", "w": w, "h": h, "x": w / 2, "y": h / 2, "filled": False, "stroke": True,
        "strokeColor": RED, "strokeWidth": 3.0, "dash": 12.0, "gap": 8.0, "cap": "butt", "join": "miter"})}
    size = max(10.0, min(h * 0.6, 1.8 * w / max(len(label), 1), 48.0))
    name = {"id": f'{node["id"]}.name', "type": "text", "props": engine_props("text", {
        "body": label, "font": F.defaults("text")["font"], "size": size, "weight": 600.0, "color": RED, "x": w / 2, "y": h / 2})}
    return {"id": node["id"], "type": "group", "props": group, **({"anim": anim} if anim else {}), "layers": [box, name]}
