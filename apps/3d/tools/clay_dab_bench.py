# Clay dab bench (3d-v2): one dab and the picture after it, in the engine program, no window. The same requests the
# viewport sends (`sculpt` dab with its `view`), on the sample scene plus a clay ball, so the core's share of a dab
# (the dab, meshing, USD, Storm's draw) can be measured and compared quickly, with Storm's counters
# (ROSTRUM3D_PERF=1). It says nothing about Qt: the real-window numbers are clay_hops.py's.
#   <venv python> apps\3d\tools\clay_dab_bench.py [--detail 0.002] [--size 0.03] [--brush add] [--moves 120]
#                                               [--mirror 1] [--out file.json]   (through heavy.ps1 ... gpu)
import argparse
import collections
import json
import math
import os
import statistics as st
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("ROSTRUM3D_PERF", "1")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "app"))
import main  # noqa: E402,F401  (puts this checkout's code first: its engine, never main's)
from rostrum_core import Document, Who  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.compile import describe  # noqa: E402
from rostrum3d.engine import Engine  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from screen3d.sample import SOURCE  # noqa: E402

W, H = 1300, 820
KEYS = ("dabMs", "applyMs", "meshMs", "usdMs", "blocks", "stormMs", "finishMs", "drawMs", "totalMs", "roundMs")


def stats(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    return {"median": round(st.median(xs), 2), "p90": round(xs[int(0.9 * (len(xs) - 1))], 2), "max": round(xs[-1], 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--detail", type=float, default=0.002)
    ap.add_argument("--size", type=float, default=0.03)
    ap.add_argument("--radius", type=float, default=0.1)
    ap.add_argument("--brush", default="add")
    ap.add_argument("--moves", type=int, default=120)
    ap.add_argument("--mirror", type=int, default=1)
    ap.add_argument("--selected", type=int, default=0)
    ap.add_argument("--static", type=int, default=0, help="1: the same picture redrawn, no dabs (Storm's floor)")
    ap.add_argument("--lights", type=int, default=1, help="0: the view without the scene's lights (no sun shadow)")
    ap.add_argument("--drop", default="", help="item ids left out of the scene (comma separated), e.g. vase")
    ap.add_argument("--png", default="", help="the last picture saved there")
    ap.add_argument("--wide", type=int, default=0, help="1: the camera far enough to see the whole set (the glass)")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    folder = Path(tempfile.mkdtemp(prefix="rostrum-dabbench-"))
    doc = Document.new(KIND, folder=folder, item="scene")
    doc.run_script("sample.py", run_source(SOURCE, "sample.py"))
    at = [0.35, a.radius, 0.45]
    doc.apply([{"op": "clay.add", "args": {"id": "lump", "at": at, "radius": a.radius}}], Who.person())
    doc.apply({"op": "clay.set", "target": ["lump"], "args": {"detailMode": "fixed", "detail": a.detail}}, Who.person())
    scene = describe(doc.data, "hero", folder)
    drop = set(filter(None, a.drop.split(",")))

    def keep(items):
        return [{**i, **({"children": keep(i["children"])} if "children" in i else {})} for i in items if i["id"] not in drop]
    scene["items"] = keep(scene["items"])
    d = a.radius * (14 if a.wide else 4.2)
    cam = {"eye": [at[0] + 0.3 * d, at[1] + 0.35 * d, at[2] + d], "target": at, "fov": 35, "frame": 0,
           "width": W, "height": H}
    view = {**cam, "renderer": "storm", "view": "", "exposure": 0.0, "studio": 1.0, "sceneLights": bool(a.lights),
            "ao": 1.0, "dof": True, "selected": ["lump"] if a.selected else []}
    recs, perf = [], collections.defaultdict(list)
    import rostrum3d
    assert Path(rostrum3d.__file__).resolve().is_relative_to(HERE.parents[2]), rostrum3d.__file__
    with Engine() as eng:
        out = eng.ensure_scene(scene)
        info = eng.clay_info("lump")
        eng.view(**view)[0].release()
        r_px = H * 0.18                                   # zigzag across the middle of the ball
        brush = {"brush": a.brush, "size": a.size, "strength": 0.5, "mirror": bool(a.mirror), "accumulate": False,
                 "falloff": 0.5, "spacing": 0.3, "frontOnly": True, "invert": False}
        eng._request({"info": {}})                       # ROSTRUM3D_TRACE: the trace so far written, a new one begun
        for i in range(a.moves if a.static else 0):
            pic = eng.view(**{**view, "eye": [cam["eye"][0] + 1e-4 * (i % 2), *cam["eye"][1:]]})
            t = pic[4].get("timing", {})
            pic[0].release()
            recs.append({"stormMs": t.get("stormMs"), "drawMs": t.get("drawMs"), "totalMs": t.get("totalMs")})
            for k, x in (pic[4].get("perf") or {}).items():
                perf[k].append(x)
            del pic
        for stroke in range(0 if a.static else 2):
            pts = []
            for i in range(a.moves):
                k = i % 48
                u = k / 24 if k < 24 else 2 - k / 24
                pts.append([round(W / 2 - r_px + 2 * r_px * u, 1),
                            round(H / 2 + 0.3 * r_px * ((i // 48) % 3 - 1) + 20 * stroke, 1)])
            eng.sculpt(item="lump", phase="begin", points=[pts[0]], **cam, **brush)
            for p in pts[1:]:
                rep, pic = eng.sculpt_view(view, item="lump", phase="dab", points=[p], **cam)
                v = pic[4] if pic else {}
                if pic:
                    pic[0].release()
                del pic
                t = v.get("timing", {})
                rec = {**{k: rep.get(k) for k in KEYS}, "roundMs": rep.get("ms"), "drawMs": t.get("drawMs"),
                       "stormMs": t.get("stormMs"), "finishMs": t.get("finishMs"), "totalMs": t.get("totalMs")}
                recs.append(rec)
                for k, x in (v.get("perf") or {}).items():
                    perf[k].append(x)
            eng.sculpt(item="lump", phase="end", folder=str(folder), points=[], **cam)
        eng._request({"info": {}})                       # ROSTRUM3D_TRACE: the dabs' trace
        if a.png:
            from PySide6.QtGui import QImage
            mv, w, h, stride, _ = eng.view(**view)
            QImage(bytes(mv), w, h, stride, QImage.Format.Format_RGBA8888).copy().save(a.png)
            mv.release()
    report = {"args": vars(a), "clay": info, "scene": {k: out.get(k) for k in ("items", "prims")} if isinstance(out, dict) else None,
              "hops": {k: stats([r.get(k) for r in recs]) for k in KEYS},
              "perf": {k: stats(v) | {"n": len(v)} for k, v in sorted(perf.items())}}
    print(json.dumps(report, indent=1))
    if a.out:
        Path(a.out).write_text(json.dumps(report, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
