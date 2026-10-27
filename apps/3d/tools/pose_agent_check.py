# CL5: the five-minute wave as an agent does it, through the MCP tools alone (run_script, edit_document, look_frame):
# a pear body drawn on the ground, an arm drawn from its side (mirrored), two small feet; pose.find_joints; both feet
# held; the right hand dragged up. Then the checks the brief names (the arm bends at shoulder and elbow, held feet and
# the body stay; two drags at two times give keys; a reshape finds the joints again and keeps a joint moved by hand)
# and the pictures: rest, waving, two times of an animated wave, after the reshape.
#   heavy.ps1 run "sam: cl5 agent check" gpu <venv python> apps\3d\tools\pose_agent_check.py <out folder>
# Exit 0 = every check passed. Puts this checkout's Python first, so it runs this checkout's engine.
import json
import math
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HERE / "python"), str(HERE / "app")]
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Sam\.rostrum\waves\results\3d-cl5\agent")

from rostrum_core import Who  # noqa: E402
from rostrum_core.mcp import Runtime  # noqa: E402
from rostrum3d.mcp.server import app_tools, make_app  # noqa: E402

FAILS: list[str] = []

SCENE = '''
floor = material("floor", baseColor="#3a3d42", roughness=0.8)
mesh("ground", shape="plane", width=6, depth=6, material=floor)
light("key", kind="rect", width=1.2, height=0.8, intensity=6, temperature=5200, x=1.4, y=1.6, z=1.2).aim((0, 0.3, 0))
light("sky", kind="dome", color="#9fb2cc", intensity=0.25)
cam = camera("cam", focalLength=35, y=0.45, z=2.2).aim((0, 0.32, 0))
shot("s", camera=cam, fps=24, start=0, end=48)
'''


def check(ok, what):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        FAILS.append(what)


def pear(cx, cy, rx, ry, n=40):
    """A pear outline on the z = 0 plane (metres): wider at the bottom."""
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        s = math.sin(t)
        w = rx * (1.0 - 0.22 * s)
        pts.append((round(cx + w * math.cos(t), 4), round(cy + ry * s, 4), 0.0))
    return pts


def oval(cx, cy, a, b, n=24):
    return [(round(cx + a * math.cos(2 * math.pi * i / n), 4), round(cy + b * math.sin(2 * math.pi * i / n), 4), 0.0)
            for i in range(n)]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="rostrum-cl5-agent-"))
    app = make_app(str(project), ["scene"])
    rt = Runtime(app, app_tools())
    who = Who.agent("cl5-check")
    report = {"steps": [], "pictures": {}}

    def call(tool, args):
        out, _ = rt.call(tool, {"item": "scene", **args}, who)
        report["steps"].append({"tool": tool, "ok": out.get("ok"), "summary": out.get("summary", "")[:400]})
        if not out.get("ok"):
            raise RuntimeError(f"{tool} failed: {out.get('summary')}")
        return out

    def ops(*calls, label=None):
        return call("edit_document", {"ops": list(calls), **({"label": label} if label else {})})

    def look(name, frame=0):
        out = call("look_frame", {"shot": "s", "frame": frame, "quality": "fast", "width": 960})
        src = Path(out["files"][0])
        dst = OUT / f"{name}.png"
        shutil.copyfile(src, dst)
        report["pictures"][name] = str(dst)

    doc = app.documents["scene"] if hasattr(app, "documents") else app.docs["scene"]

    def clay():
        return doc.item("buddy")

    def bones(item=None):
        out, stack = {}, list((item or clay()).get("bones", []))
        while stack:
            b = stack.pop()
            out[b.get("joint") or b["id"]] = b
            stack += b.get("bones", [])
        return out

    try:
        arm = oval(-0.24, 0.30, 0.14, 0.035)         # the character's right arm (-x), starting inside the body's side
        foot = oval(-0.07, 0.025, 0.05, 0.03)
        call("run_script", {"source": SCENE + f'''
c = clay("buddy", draw={pear(0.0, 0.26, 0.15, 0.24)}, symmetry="x", name="Buddy")
o = (c.node.get("x", 0.0), c.node.get("y", 0.0), c.node.get("z", 0.0))
def here(pts):
    return [(x - o[0], y - o[1], z - o[2]) for x, y, z in pts]
c.draw(here({arm}), name="arm")
c.draw(here({foot}), name="foot")
'''})
        look("01-rest")

        found = ops({"op": "pose.find_joints", "target": ["buddy"], "args": {}})
        js = bones()
        (OUT / "grid48.json").write_text(json.dumps(app.state.engine.clay_grid("buddy", 48)), encoding="utf-8")
        report["joints"] = {k: {"head": [b.get("x"), b.get("y"), b.get("z")], "length": b.get("length")} for k, b in js.items()}
        check({"arm.R", "forearm.R", "arm.L", "forearm.L", "foot.L", "foot.R"} <= set(js),
              f"the joints found name both arms (arm + forearm) and both feet ({sorted(js)})")

        ops({"op": "pose.hold", "target": ["buddy"], "args": {"bone": "foot.L"}},
            {"op": "pose.hold", "target": ["buddy"], "args": {"bone": "foot.R"}}, label="Hold both feet")
        before = {k: [b.get(f) for f in ("rx", "ry", "rz")] for k, b in bones().items()}
        hand_up = [-0.20, 0.50, 0.06]
        ops({"op": "pose.drag", "target": ["buddy"], "args": {"part": "forearm.R", "to": hand_up, "at": 0}},
            label="Wave")
        moved = {k for k, b in bones().items() if b.get("keys")}
        report["moved"] = sorted(moved)
        check({"arm.R", "forearm.R"} <= moved, f"the wave bends the right arm at the shoulder AND the elbow ({sorted(moved)})")
        check(not ({"foot.L", "foot.R", "body"} & moved), "the held feet and the body did not turn")
        look("02-wave")

        # Animate: a second drag at another time; the keys at 0 and 1 s give the movement between
        ops({"op": "pose.drag", "target": ["buddy"], "args": {"part": "forearm.R", "to": [-0.45, 0.50, 0.05], "at": 1.0}},
            label="Wave, 1 s")
        keyed = {k: sorted({round(kk["t"], 3) for kk in b.get("keys", [])}) for k, b in bones().items() if b.get("keys")}
        report["keys"] = keyed
        check(any(v == [0.0, 1.0] for v in keyed.values()), f"two drags at two times keyed 0 s and 1 s ({keyed})")
        for f in (0, 6, 12, 18, 24):
            look(f"03-anim-f{f:02d}", frame=f)

        # a joint moved by hand, then a reshape: the joints are found again and that joint stays where it was put
        elbow = bones()["forearm.L"]
        report["elbowBefore"] = [elbow.get("x"), elbow.get("y"), elbow.get("z")]
        ops({"op": "pose.move_joint", "target": ["buddy"], "args": {"joint": "forearm.L", "to": [0.33, 0.30, 0.0]}})
        placed = bones()["forearm.L"]
        check(bool(placed.get("placed")), "a joint moved by hand is marked placed")
        key_before = clay().get("jointsKey")
        it = clay()
        top = [0.0 - it.get("x", 0.0), 0.52 - it.get("y", 0.0), 0.0 - it.get("z", 0.0)]
        ops({"op": "clay.lump", "target": ["buddy"], "args": {"at": top, "radius": 0.07}}, label="Head bump")
        out_of_date = __import__("rostrum3d.pose_joints", fromlist=["x"]).out_of_date(clay(), doc.data)
        check(out_of_date, "after the reshape the joints are marked out of date")
        ops({"op": "pose.find_joints", "target": ["buddy"], "args": {}})
        again = bones()
        check(clay().get("jointsKey") != key_before, "the joints were found again (a new key)")
        check(bool(again.get("forearm.L", {}).get("placed")), "the placed elbow is kept after finding again")
        check(any(b.get("keys") for b in again.values()), "the wave's keys stay after finding again")
        look("04-after-reshape")
        report["found"] = found.get("summary", "")
    except Exception as e:  # noqa: BLE001
        FAILS.append(f"the run stopped: {type(e).__name__}: {e}")
    finally:
        report["fails"] = FAILS
        (OUT / "pose_agent_check.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
        try:
            app.state.engine.close()
        except Exception:  # noqa: BLE001
            pass
        shutil.rmtree(project, ignore_errors=True)
    print(f"{len(FAILS)} failed; pictures in {OUT}")
    for f in FAILS:
        print("  " + f)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
