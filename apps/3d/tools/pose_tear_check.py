# CL7b: a raised arm must leave the body closed and smooth (the chest tore open under CL7's hard piece switch, and
# "+" stitch marks showed where the arms rest on the belly and the feet against the body). Through the MCP tools: a
# pear body, an arm resting along the belly (mirrored), two feet; pose.find_joints; both feet held; the right hand
# dragged high above the shoulder (past its reach, so the chest turns too, as in the walk). Pictures, Quick (Storm)
# and Final (Cycles): the front (the belly where the other arm rests) and the raised shoulder from the side.
# Numbers (on the clay's own grid, by skin_parts.weights, the core's rule in Python): a closed surface of the
# clay posed with the core's bone moves (dual-quaternion, as clay_skin.cpp), its worst edge stretch and its worst
# weight change per cm, beside the plain nearest-bones rule's; and the hip's arm share (CL7's win: ~0).
#   heavy.ps1 run "hem: cl7b tear check" gpu <venv python> apps\3d\tools\pose_tear_check.py <out folder>
# Exit 0 = the checks passed. Puts this checkout's Python first, so it runs this checkout's engine.
import json
import math
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HERE / "python"), str(HERE / "app")]
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Sam\.rostrum\waves\results\3d-cl7b\tear")

from rostrum_core import Who  # noqa: E402
from rostrum_core.mcp import Runtime  # noqa: E402
from rostrum3d import pose_ik, pose_joints as PJ, skin, skin_parts as SP  # noqa: E402
from rostrum3d.mcp.server import app_tools, make_app  # noqa: E402

FAILS: list[str] = []

SCENE = '''
floor = material("floor", baseColor="#3a3d42", roughness=0.8)
mesh("ground", shape="plane", width=6, depth=6, material=floor)
light("key", kind="rect", width=1.2, height=0.8, intensity=6, temperature=5200, x=1.4, y=1.6, z=1.2).aim((0, 0.3, 0))
light("fill", kind="rect", width=1.0, height=0.8, intensity=3, x=-1.6, y=1.0, z=0.6).aim((0, 0.3, 0))
light("sky", kind="dome", color="#9fb2cc", intensity=0.25)
front = camera("cam_front", focalLength=35, y=0.4, z=1.7).aim((0, 0.3, 0))
side = camera("cam_side", focalLength=50, x=-1.1, y=0.45, z=0.35).aim((-0.12, 0.33, 0))
shot("front", camera=front, fps=24, start=0, end=1)
shot("side", camera=side, fps=24, start=0, end=1)
'''


def check(ok, what):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        FAILS.append(what)


def pear(cx, cy, rx, ry, n=40):
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        w = rx * (1.0 - 0.22 * math.sin(t))
        pts.append((round(cx + w * math.cos(t), 4), round(cy + ry * math.sin(t), 4), 0.0))
    return pts


def oval(cx, cy, a, b, tilt=0.0, n=24):
    c, s = math.cos(tilt), math.sin(tilt)
    out = []
    for i in range(n):
        x, y = a * math.cos(2 * math.pi * i / n), b * math.sin(2 * math.pi * i / n)
        out.append((round(cx + c * x - s * y, 4), round(cy + s * x + c * y, 4), 0.0))
    return out


# --- the numbers: a closed surface of the clay's grid, posed as the core poses it
def surface(occ, origin, cell, up=3):
    """A welded closed mesh (voxel faces at cell / up) of the smoothed inside, clay space."""
    from scipy import ndimage
    f = ndimage.gaussian_filter(ndimage.zoom(occ.astype(np.float32), up, order=1), up * 0.6) > 0.5
    c = cell / up
    o = np.asarray(origin) + cell / 2 - c / 2
    verts, quads = {}, []
    pad = np.pad(f, 1).astype(np.int8)
    for ax in range(3):
        a1, a2 = [x for x in range(3) if x != ax]
        for s in (1, -1):
            for idx in np.argwhere(np.diff(pad, axis=ax) == s):
                base = idx - 1
                base[ax] += 1
                q = []
                for u, v in ((0, 0), (1, 0), (1, 1), (0, 1)):
                    p = base.copy()
                    p[a1] += u
                    p[a2] += v
                    q.append(verts.setdefault(tuple(p), len(verts)))
                quads.append(q if s > 0 else q[::-1])
    P = np.zeros((len(verts), 3))
    for k, n in verts.items():
        P[n] = o + (np.array(k) - 0.5) * c
    q = np.array(quads)
    return P, np.r_[q[:, [0, 1, 2]], q[:, [0, 2, 3]]]


def pose_dq(P, W, moves):
    """Dual-quaternion blend, signs lined up with the heaviest bone (clay_skin.cpp)."""
    from scipy.spatial.transform import Rotation as R

    def mul(a, b):
        w1, x1, y1, z1 = a.T
        w2, x2, y2, z2 = b.T
        return np.stack([w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2, w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                         w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2, w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2], -1)
    q = R.from_matrix([np.array(m[:9]).reshape(3, 3) for m in moves]).as_quat()
    Q = np.c_[q[:, 3], q[:, :3]]
    D = 0.5 * mul(np.array([np.r_[0, m[9:]] for m in moves]), Q)
    sgn = np.sign(Q @ Q.T)[np.argmax(W, 1)]
    sgn[sgn == 0] = 1
    r, d = (W * sgn) @ Q, (W * sgn) @ D
    n = np.linalg.norm(r, axis=1, keepdims=True)
    r, d = r / n, d / n
    t = 2 * mul(d, r * np.array([1, -1, -1, -1]))[:, 1:]
    return R.from_quat(np.c_[r[:, 1:], r[:, 0]]).apply(P) + t


def numbers(grid, clay, report):
    occ = PJ.occupancy(grid)
    V, tris = surface(occ, grid["origin"], grid["cell"])
    core = skin.skin(clay, [0.0])
    rest, parts = core["rest"], core["parts"]
    moves = pose_ik.chain_pose(clay)
    names = [b.get("joint") or "" for b, _ in skin.bones_of(clay)]
    arm = [i for i, n in enumerate(names) if n.startswith(("arm.", "forearm.", "hand."))]
    e = np.unique(np.sort(np.r_[tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]], 1), axis=0)
    l0 = np.linalg.norm(V[e[:, 0]] - V[e[:, 1]], axis=1)
    out = {}
    for rule, p in (("plain", None), ("pieces", parts)):
        W = np.zeros((len(V), len(rest)))
        for i, w in enumerate(SP.weights(V, rest, p)):
            for b, x in w.items():
                W[i, b] = x
        V1 = pose_dq(V, W, moves)
        st = np.linalg.norm(V1[e[:, 0]] - V1[e[:, 1]], axis=1) / l0
        jump = np.abs(W[e[:, 0]] - W[e[:, 1]]).sum(1) / l0 / 100
        hip = sum(x for b, x in SP.weights([[-0.085, 0.09, 0.03]], rest, p)[0].items() if b in arm)
        out[rule] = {"maxStretch": round(float(st.max()), 2), "edgesOver3x": int((st > 3).sum()),
                     "stretchP999": round(float(np.quantile(st, 0.999)), 2),
                     "maxWeightChangePerCm": round(float(jump.max()), 2), "hipArmShare": round(float(hip), 3)}
        print(rule, out[rule])
    report["numbers"] = out
    pl, pc = out["plain"], out["pieces"]
    check(pc["maxWeightChangePerCm"] <= 1.5 * pl["maxWeightChangePerCm"] + 0.5,
          f"no hard switch: the weights change at most {pc['maxWeightChangePerCm']}/cm "
          f"(plain rule {pl['maxWeightChangePerCm']}/cm; CL7's switch was ~7/cm)")
    check(pc["hipArmShare"] < 0.02, f"the hip stays the body's ({pc['hipArmShare']:.3f} arm)")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="rostrum-cl7b-tear-"))
    app = make_app(str(project), ["scene"])
    rt = Runtime(app, app_tools())
    who = Who.agent("cl7b-check")
    report = {"steps": [], "pictures": {}}

    def call(tool, args):
        out, _ = rt.call(tool, {"item": "scene", **args}, who)
        report["steps"].append({"tool": tool, "ok": out.get("ok"), "summary": out.get("summary", "")[:400]})
        if not out.get("ok"):
            raise RuntimeError(f"{tool} failed: {out.get('summary')}")
        return out

    def ops(*calls, label=None):
        return call("edit_document", {"ops": list(calls), **({"label": label} if label else {})})

    def look(name):
        for shot in ("front", "side"):
            for q in ("fast", "final"):
                out = call("look_frame", {"shot": shot, "frame": 0, "quality": q, "width": 960})
                for _ in range(40):                        # over 25 s it became a job: wait for it (up to ~15 min)
                    job = (out.get("data") or {}).get("job_id")
                    if out.get("files") or not job:
                        break
                    out, _ = rt.call("inspect_job", {"job_id": job, "wait_s": 25}, who)
                    if not out.get("ok", True):
                        raise RuntimeError(f"look_frame {shot} {q} failed: {out.get('summary')}")
                if not out.get("files"):
                    raise RuntimeError(f"look_frame {shot} {q} gave no picture: {out.get('summary', '')[:300]}")
                dst = OUT / f"{name}-{shot}-{'quick' if q == 'fast' else 'final'}.png"
                shutil.copyfile(Path(out["files"][0]), dst)
                report["pictures"][dst.stem] = str(dst)

    doc = app.documents["scene"] if hasattr(app, "documents") else app.docs["scene"]
    try:
        arm = oval(-0.155, 0.24, 0.11, 0.032, tilt=0.9)   # the right arm, from the side down along the belly
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
        ops({"op": "pose.find_joints", "target": ["buddy"], "args": {}})
        grid = app.state.engine.clay_grid("buddy", 48)
        (OUT / "grid48.json").write_text(json.dumps(grid), encoding="utf-8")
        it = doc.item("buddy")
        o = np.array([it.get("x", 0.0), it.get("y", 0.0), it.get("z", 0.0)])
        js = {j["joint"]: j for j in PJ.joints_of(it)}
        report["joints"] = sorted(js)
        check({"arm.R", "forearm.R", "foot.L", "foot.R"} <= set(js), f"the joints found ({sorted(js)})")
        ops({"op": "pose.hold", "target": ["buddy"], "args": {"bone": "foot.L"}},
            {"op": "pose.hold", "target": ["buddy"], "args": {"bone": "foot.R"}}, label="Hold both feet")
        sh = np.array(js["arm.R"]["head"])
        reach = sum(float(np.linalg.norm(np.array(js[n]["tail"]) - np.array(js[n]["head"])))
                    for n in ("arm.R", "forearm.R", "hand.R") if n in js)
        up = np.array([-0.3, 1.0, 0.15]) / np.linalg.norm([-0.3, 1.0, 0.15])
        to = (o + sh + up * reach * 1.3).round(4).tolist()        # past its reach: the chest turns too
        last = "hand.R" if "hand.R" in js else "forearm.R"
        ops({"op": "pose.drag", "target": ["buddy"], "args": {"part": last, "to": to, "at": 0}}, label="Wave")
        look("02-wave")
        numbers(grid, doc.item("buddy"), report)
    except Exception as e:  # noqa: BLE001
        FAILS.append(f"the run stopped: {type(e).__name__}: {e}")
    finally:
        report["fails"] = FAILS
        (OUT / "pose_tear_check.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
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
