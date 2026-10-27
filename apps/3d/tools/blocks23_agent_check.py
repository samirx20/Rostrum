# Brief 23 agent check: an agent builds a material's blocks with edit_document (graph.add + graph.connect: a Noise
# block's value into the Surface's Roughness) and checks it with look_material in Quick and Final, as an agent does.
# Through the lock:
#   heavy.ps1 run "<team>: 3d-23 agent" gpu C:\Users\Sam\.rostrum\venv\Scripts\python.exe -I apps\3d\tools\blocks23_agent_check.py [out]
# Writes agent-quick.png / agent-final.png (look_material's turntable strips) and prints each reply's summary.
import json
import shutil
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(WT / "apps" / "3d" / "python"), str(WT / "shared" / "core")]
from rostrum_core import Document, Who                        # noqa: E402
from rostrum_core.mcp import Runtime                          # noqa: E402
from rostrum3d import KIND, run_source                        # noqa: E402
from rostrum3d.mcp.server import app_tools, make_app          # noqa: E402

SCRATCH = Path(r"C:\Users\Sam\.rostrum\waves\scratch\hem-3d23-lead\agent")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Sam\.rostrum\waves\results\3d-23")
ITEM = "agent"
SCENE = '''
ball = material("ball", start="Glossy plastic", baseColor="#2f5fb3")
floor = material("floor", baseColor="#7d8088", roughness=0.8)
mesh("plinth", shape="box", width=1.2, height=0.02, depth=0.9, y=-0.01, material=floor)
mesh("b", name="Ball", shape="sphere", radius=0.12, y=0.12, material=ball)
light("key", kind="rect", width=0.6, height=0.4, intensity=25, x=-0.4, y=0.7, z=0.6).aim((0, 0.1, 0))
light("sky", kind="dome", color="#b8c4d6", intensity=0.3)
cam = camera("cam", focalLength=40, y=0.3, z=0.7).aim((0, 0.1, 0))
shot("hero", camera=cam, fps=24, start=0, end=1, width=1280, height=720)
'''


def call(rt, who, tool, args):
    reply, _ = rt.call(tool, args, who)
    while reply["ok"] and reply["data"].get("status") not in (None, "done"):
        reply, _ = rt.call("inspect_job", {"job_id": reply["data"]["job_id"], "wait_s": 25}, who)
    print(tool, "->", reply["summary"], flush=True)
    if not reply["ok"]:
        raise SystemExit(f"{tool} failed")
    return reply


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True)
    (SCRATCH / "project.json").write_text('{"items": []}', encoding="utf-8")
    doc = Document.new(KIND, str(SCRATCH), ITEM)
    doc.run_script("scene.py", run_source(SCENE, "scene.py"))
    doc.save()
    OUT.mkdir(parents=True, exist_ok=True)
    app = make_app(str(SCRATCH), documents={ITEM: doc})
    rt, who = Runtime(app, app_tools()), Who.agent("blocks23_agent_check")
    try:
        call(rt, who, "edit_document", {"item": ITEM, "label": "noisy roughness", "ops": [
            {"op": "graph.add", "target": ["ball"], "args": {"type": "noise", "id": "noise_1", "x": -320, "y": 0,
                                                             "values": {"scale": 18, "detail": 3}}},
            {"op": "graph.connect", "target": ["ball"], "args": {"from": "noise_1.value", "to": "surface.roughness"}}]})
        found = {}
        for quality, name in (("fast", "agent-quick.png"), ("final", "agent-final.png")):
            r = call(rt, who, "look_material", {"item": ITEM, "material": "ball", "quality": quality, "count": 4})
            shutil.copyfile(next(f for f in r["files"] if f.endswith(".png")), OUT / name)
            data = r["data"].get("result", r["data"])          # a long tool's reply comes through its job
            found[quality] = {"renderer": data["renderer"], "blocks": data.get("blocks")}
        wires = found["final"]["blocks"]["wires"] if found["final"]["blocks"] else []
        ok = any(w["from"] == "noise_1.value" and w["to"] == "surface.roughness" for w in wires)
        print(json.dumps(found, indent=1))
        print("CHECK the wire Noise.value -> Surface.roughness is in look_material's reply:", "ok" if ok else "FAIL")
        (OUT / "agent_check.json").write_text(json.dumps({"ok": ok, **found}, indent=1), encoding="utf-8")
        if not ok:
            raise SystemExit(1)
    finally:
        app.state.engine.close()
