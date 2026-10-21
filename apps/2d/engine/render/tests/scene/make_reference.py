"""Writes reference.json beside this file: what the Python layer's evaluator (the contract's reference) gives for a
small scene, so scene/tests.rs can check the engine gives the same numbers and the same frame.

    .venv\\Scripts\\python.exe apps\\2d\\engine\\render\\tests\\scene\\make_reference.py

Run it again when easing.py, evaluate.py, fields.py or stopgap_html.py change.
"""
import json
from pathlib import Path

from rostrum2d import easing, fields as F, stopgap_html
from rostrum2d.scene import FORMAT, VERSION, frame_at


def item(id, type, anim=None, **props):
    node = {"id": id, "type": type, "props": {**F.defaults(type), **props}}
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


STAGE_T = 0.8
out = {
    "fields": {t: [kinds(p) for p in ps] for t, ps in F.FIELDS.items() if t != "key"},
    "animatable": {t: F.animatable(t) for t in F.FIELDS if t != "key"},
    "eases": eases,
    "scene": scene,
    "frames": [frame_at(scene, t) for t in times],
    "stage_t": STAGE_T,
    "stage": stopgap_html.stage(frame_at(scene, STAGE_T), frozenset({"gradient-text"})),
}
Path(__file__).with_name("reference.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print(f"{len(eases)} ease values, {len(times)} frames")
