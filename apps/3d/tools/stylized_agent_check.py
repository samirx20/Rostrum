# Brief 22 agent check: an agent gives the case Lines + Light to colour with edit_document (material.set) and sees it
# with look_frame renderer "stylized", as an agent does. Through the lock:
#   heavy.ps1 run "<team>: 3d-22 agent" gpu C:\Users\Sam\.rostrum\venv\Scripts\python.exe -I apps\3d\tools\stylized_agent_check.py [out]
# Writes agent-before.png / agent-after.png (the stylized look before and after the edit) and prints each reply.
import shutil, sys
from pathlib import Path

WT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(WT / "apps" / "3d" / "python"), str(WT / "shared" / "core")]
from rostrum_core import Document, Who                        # noqa: E402
from rostrum_core.mcp import Runtime                          # noqa: E402
from rostrum3d import KIND, run_source                        # noqa: E402
from rostrum3d.mcp.server import app_tools, make_app          # noqa: E402

SCRATCH = Path(r"C:\Users\Sam\.rostrum\waves\scratch\sam-3d22-lead\agent")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Sam\.rostrum\waves\results\3d-22")
ITEM = "agent"
SCENE = '''
shell = material("shell", baseColor="#c8553d", roughness=0.45)
floor = material("floor", baseColor="#7d8088", roughness=0.8)
mesh("plinth", shape="box", width=1.2, height=0.02, depth=0.9, y=-0.01, z=-0.1, material=floor)
mesh("case", name="Case", shape="box", width=0.24, height=0.08, depth=0.16, bevel=0.008, segments=3, y=0.04, ry=35, material=shell)
light("key", kind="rect", width=0.6, height=0.4, intensity=25, x=-0.4, y=0.7, z=0.6).aim((0, 0.05, 0))
light("sky", kind="dome", color="#b8c4d6", intensity=0.3)
cam = camera("cam", focalLength=40, y=0.3, z=0.55).aim((0, 0.04, 0))
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
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True)
    (SCRATCH / "project.json").write_text('{"items": []}', encoding="utf-8")
    doc = Document.new(KIND, str(SCRATCH), ITEM)
    doc.run_script("scene.py", run_source(SCENE, "scene.py"))
    doc.save()
    OUT.mkdir(parents=True, exist_ok=True)
    app = make_app(str(SCRATCH), documents={ITEM: doc})
    rt, who = Runtime(app, app_tools()), Who.agent("stylized_agent_check")
    try:
        look = {"item": ITEM, "shot": "hero", "renderer": "stylized", "width": 960}
        before = call(rt, who, "look_frame", look)
        shutil.copyfile(next(f for f in before["files"] if f.endswith(".png")), OUT / "agent-before.png")
        call(rt, who, "edit_document", {"item": ITEM, "label": "ink the case", "ops": [
            {"op": "material.set", "target": ["shell"],
             "args": {"lines": True, "linesWidth": 3, "lightToColor": True, "shadowColor": "#5b4f7a"}}]})
        after = call(rt, who, "look_frame", look)
        shutil.copyfile(next(f for f in after["files"] if f.endswith(".png")), OUT / "agent-after.png")
        print(OUT / "agent-after.png")
    finally:
        app.state.engine.close()
