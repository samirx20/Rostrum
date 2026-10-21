import json, sys
src = open(r"C:\Users\Sam\.rostrum\waves\scratch\sam-S8-lead\proof\film.py", encoding="utf-8").read()
P = lambda x, y, **h: {"op": "path.add_point", "target": ["swoosh"], "args": {"x": x, "y": y, **h}}
S = lambda i, **h: {"op": "path.set_point", "target": ["swoosh"], "args": {"i": i, **h}}
OUT = r"C:\Users\Sam\.rostrum\waves\results\stage2\2d-design"
build = [
 {"tool": "run_script", "args": {"source": src, "name": "launch.py"}},
 {"tool": "edit_document", "args": {"label": "Pen: swoosh", "ops": [
   {"op": "layer.add", "target": ["launch"], "args": {"type": "path", "id": "swoosh", "index": 2}},
   {"op": "path.set", "target": ["swoosh"], "args": {"x": 0, "y": 0, "anchorX": 0, "anchorY": 0, "w": 1920, "h": 1080,
     "filled": False, "stroke": True, "strokeWidth": 7, "cap": "round", "join": "round"}},
   P(-60, 820), P(760, 300, inX=-280, inY=0), P(1420, 700, inX=-300, inY=0), P(1990, 260, inX=-190, inY=170),
   S(0, outX=360, outY=-30), S(1, outX=300, outY=0, mirror=True), S(2, outX=220, outY=0),
 ]}},
 {"tool": "edit_document", "args": {"label": "Swoosh look", "ops": [
   {"op": "path.fit", "target": ["swoosh"], "args": {}},
   {"op": "effect.add", "target": ["swoosh"], "args": {"type": "gradient", "id": "swoosh_grad"}},
   {"op": "gradient.set", "target": ["swoosh_grad"], "args": {"angle": 90, "color1": "#ffb800", "color2": "#38d9ff", "middle": True, "color3": "#ff3d71", "mid": 0.5}},
   {"op": "effect.add", "target": ["swoosh"], "args": {"type": "glow", "id": "swoosh_glow"}},
   {"op": "glow.set", "target": ["swoosh_glow"], "args": {"radius": 22, "strength": 0.9}},
   {"op": "key.add", "target": ["swoosh"], "args": {"prop": "trimEnd", "t": 0.0, "v": 0, "ease": "snappy"}},
   {"op": "key.add", "target": ["swoosh"], "args": {"prop": "trimEnd", "t": 1.4, "v": 1}},
 ]}},
]
looks = [{"tool": "look_frame", "args": {"time": t, "width": 1280}} for t in (0.5, 1.2, 2.2, 2.6, 3.6)]
final = [{"tool": "look_sheet", "args": {}}, {"tool": "look_motion", "args": {}},
         {"tool": "render_video", "args": {"path": OUT + r"\launch-title-4s.mp4"}}]
which = sys.argv[1]
calls = {"build": build + looks, "final": final}[which]
json.dump(calls, open(rf"C:\Users\Sam\.rostrum\waves\scratch\sam-S8-lead\proof\{which}.json", "w", encoding="utf-8"), indent=1)
