"""Writes reference.json beside this file: what the Python layer's evaluator (the contract's reference) gives for a
small scene, so scene/tests.rs can check the engine gives the same numbers and the same frame.

    .venv\\Scripts\\python.exe apps\\2d\\engine\\render\\tests\\scene\\make_reference.py

Run it again when rostrum_core/keys/easing.py, evaluate.py, fields.py or stopgap_html.py change.
"""
import json
from pathlib import Path

from rostrum2d import fields as F, fill_paint
from rostrum_core.keys import easing
from rostrum2d.evaluate import resolve
from rostrum2d.scene import FORMAT, VERSION, python_only

HERE = Path(__file__).with_name("reference.json")
SCENE_TYPES = [t for t in F.FIELDS if t not in ("key", "frame", "pose", "render3d", "textstyle", "swatch", "painting")]  # a drawing's frame, a saved pose, a named text style: document items, not scene ones; a 3D render reaches the engine as a video (scene.py)


def item(id, type, anim=None, **props):
    values = {**F.defaults(type), **props}
    node = {"id": id, "type": type, "props": fill_paint.engine_props({"type": type, **values}, {k: v for k, v in values.items() if k not in python_only(type)})}
    if anim:
        node["anim"] = anim
    return node


def keys(*ks, ease="smooth", **extra):
    return [{"t": t, ("c" if isinstance(v, str) else "v"): v, "ease": ease, **extra} for t, v in ks]


card = item("card", "shape", x=120, y=120, w=160, h=90, radius=18, fill="#3a6df0", anim={
    "x": keys((0.0, 90), (1.0, 240), ease="snappy"),
    "opacity": keys((0.2, 0), (0.9, 1), ease="spring", stiffness=220, damping=9),
    "fill": keys((0.0, "#3a6df0"), (1.2, "#f04a3a"), ease="easeInOut"),
    "rotation": keys((0.0, -8), (1.5, 6), ease="custom", x1=0.3, y1=1.4, x2=0.6, y2=1.0)})
card["effects"] = [item("card_shadow", "shadow", dy=8, radius=16, strength=0.4)]
title = item("title", "text", body="Rostrum & co", size=44, weight=500, x=200, y=60, anim={
    "weight": keys((0.1, 300), (1.4, 800), ease="natural"),
    "tracking": keys((0.0, 0.08), (1.0, -0.01), ease="heavy"),
    "y": keys((0.0, 90), (0.6, 60), (1.2, 50), ease="bounce")})
title["effects"] = [item("title_grad", "gradient", color1="#ffffff", color2="#8fa8ff", angle=180),
                    item("title_glow", "glow", radius=10, ownColor=False, color="#8fa8ff",
                         anim={"strength": keys((0.3, 0), (1.0, 0.7), ease="easeOut")})]
dot = item("dot", "shape", shape="ellipse", w=40, h=40, x=60, y=190, fill="#ffd24a", start=0.3, end=1.1,
           anim={"scale": keys((0.3, 0.2), (0.8, 1.2), (1.0, 1.0), ease="easeIn")})
slot = item("slot", "group", x=300, y=180, w=160, h=80, clip=True, anim={"h": keys((0.5, 80), (0.7, 40), ease="hold")})
slot["layers"] = [item("bar", "shape", w=120, h=30, x=80, y=40, fill="#e8e8f0", anim={"y": keys((0.0, 90), (1.0, 40), ease="linear")})]
slot["masks"] = [item("wipe", "mask", x=0, y=0, w=0, h=80, anim={"w": keys((0.2, 0), (1.0, 160), ease="smooth")})]
comp = item("main", "comp", width=400, height=240, fps=30, duration=1.5, background="#101018")
comp["layers"] = [card, title, dot, slot]
scene = {"format": FORMAT, "version": VERSION, "comp": comp}

times = [0.0, 0.1, 0.25, 0.5, 0.65, 0.8, 1.0, 1.05, 1.3, 2.0]
eases = []
for name in easing.NAMES:
    extra = {"custom": {"x1": 0.3, "y1": 1.4, "x2": 0.6, "y2": 1.0}, "spring": {"stiffness": 220, "damping": 9}}.get(name, {})
    for x in [-0.1, 0.0, 0.03, 0.1, 0.25, 0.37, 0.5, 0.63, 0.75, 0.9, 0.97, 1.0]:
        key = {"ease": name, **extra}
        eases.append({"key": key, "x": x, "p": easing.ease(key, x)})


def kinds(p):
    if p.type == "choice":
        return [p.name, "choice", list(p.options)]
    return [p.name, {"number": "number", "color": "color", "toggle": "toggle", "text": "text"}[p.type], None]


def frame_at(node, t):
    """The scene at time t through evaluate.resolve: every value evaluated, layers outside start..end dropped."""
    item = {"id": node["id"], "type": node["type"], **node["props"],
            "keys": [{"prop": p, **k} for p, ks in node.get("anim", {}).items() for k in ks]}
    props = {k: v for k, v in resolve(item, t).items() if k not in python_only(node["type"])}
    out = {"id": node["id"], "type": node["type"], "props": props}
    for part in ("effects", "masks", "layers"):
        if part in node:
            out[part] = [k for k in (frame_at(c, t) for c in node[part]) if k is not None]
    p = out["props"]
    return None if node["type"] in F.LAYERS and not (p["start"] <= t < p["end"]) else out


old = json.loads(HERE.read_text(encoding="utf-8"))
out = {
    # Auto layout's and stepped timing's fields stay on the Python side (scene.python_only): the engine never sees them.
    "fields": {t: [kinds(p) for p in F.FIELDS[t] if p.name not in python_only(t)] for t in SCENE_TYPES},
    "animatable": {t: [f for f in F.animatable(t) if f not in python_only(t)] for t in SCENE_TYPES},
    "eases": eases,
    "scene": scene,
    "frames": [{"format": FORMAT, "version": VERSION, "t": t, "comp": frame_at(comp, t)} for t in times],
    "stage_t": old["stage_t"],
    "stage": old["stage"],
}
HERE.write_text(json.dumps(out, indent=1), encoding="utf-8")
print(f"{len(eases)} ease values, {len(times)} frames")
