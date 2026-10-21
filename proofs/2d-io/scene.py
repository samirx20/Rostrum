"""The H9 test scene (made by the Lottie member): a card sliding in with a spring, a fading dot changing colour,
a path drawn on, a clipped group, a text and a tilted square. Plain scene description (ENGINE_CONTRACT.md)."""
from rostrum2d import fields as F


def node(id, type, props=None, anim=None, **kw):
    n = {"id": id, "type": type, "props": {**F.defaults(type), **(props or {})}}
    if anim: n["anim"] = anim
    n.update(kw)
    return n

SCENE = {"format": "rostrum-2d-scene", "version": 1, "comp": node("test", "comp",
  {"width": 1280, "height": 720, "fps": 30, "duration": 3.0, "background": "#10131c"}, layers=[
  node("card", "shape", {"shape": "rect", "w": 400, "h": 220, "radius": 30, "fill": "#e8553d", "stroke": True,
        "strokeColor": "#ffffff", "strokeWidth": 12, "x": 400, "y": 200, "rotation": 8},
       {"x": [{"t": 0.2, "v": -300, "ease": "snappy"}, {"t": 1.2, "v": 400}],
        "scale": [{"t": 1.5, "v": 1.0, "ease": "spring", "stiffness": 170, "damping": 8}, {"t": 2.5, "v": 1.3}]}),
  node("dot", "shape", {"shape": "ellipse", "w": 160, "h": 160, "fill": "#3dc8e8", "x": 960, "y": 200},
       {"opacity": [{"t": 0.3, "v": 0.0, "ease": "easeInOut"}, {"t": 1.5, "v": 1.0, "ease": "hold"}, {"t": 2.0, "v": 0.2}],
        "fill": [{"t": 0.3, "c": "#3dc8e8", "ease": "linear"}, {"t": 2.5, "c": "#f5d742"}]}),
  node("squiggle", "path", {"d": "M0 80 C 60 0 140 0 200 80 C 260 160 340 160 400 80", "w": 400, "h": 160, "filled": False, "stroke": True,
        "strokeColor": "#9cff6b", "strokeWidth": 14, "cap": "round", "x": 640, "y": 500},
       {"trimEnd": [{"t": 0.5, "v": 0.0, "ease": "smooth"}, {"t": 2.0, "v": 1.0}]}),
  node("panel", "group", {"w": 500, "h": 200, "x": 250, "y": 540, "clip": True, "anchorX": 0, "anchorY": 0, "opacity": 0.9}, layers=[
      node("bar", "shape", {"shape": "rect", "w": 600, "h": 80, "fill": "#8a5cff", "x": 0, "y": 0, "anchorX": 0, "anchorY": 0},
           {"x": [{"t": 0.0, "v": -400, "ease": "natural"}, {"t": 1.0, "v": 0}]}),
      node("tri", "path", {"d": "M0 0 L80 0 L40 70 Z", "w": 80, "h": 70, "fill": "#ffffff", "x": 400, "y": 140}),
  ]),
  node("lbl", "text", {"body": "Hello"}),
  node("tilted", "shape", {"tiltX": 20, "w": 50, "h": 50, "x": 100, "y": 100}),
]) }
