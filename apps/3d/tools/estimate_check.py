"""Proves the render time estimate is honest: for a still (1920x1080, good = 128 samples), a 24-frame mp4 at full size (draft = 32
samples) and the same at half size (re-scaled from the same kept probe, no new one) of one small moving scene, the estimate (estimate_job.measure on a fresh scratch cache + estimate.scale) is set against a real
render made the way the Render button does it (a NEW Engine, wall-clock from creating it to the last file written, the mp4 encode
included). Prints a table (with the probe's own wall time) and writes estimate_check.json (estimate, real, error %, per-frame figures, the measurement).
Through the lock: heavy.ps1 run "<team>: estimate check" gpu <python> apps/3d/tools/estimate_check.py (PYTHONPATH apps/3d/python;shared/core;shared/gui-kit)."""
import json, os, shutil, sys, tempfile, threading, time
from pathlib import Path

OUT = Path(tempfile.gettempdir()) / "rostrum3d_estimate_check"
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir(parents=True)
os.environ["ROSTRUM_CACHE_DIR"] = str(OUT / "cache")            # fresh cache: the probe really measures (before rostrum_core is imported)
WT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(WT / "apps" / "3d" / "python"), str(WT / "shared" / "core")]
from rostrum_core import Document                                # noqa: E402
from rostrum3d import KIND, run_source, estimate_job, gpu_busy  # noqa: E402
from rostrum3d.compile import describe, shot_info               # noqa: E402
from rostrum3d.engine import Engine                             # noqa: E402
from rostrum3d.render_fields import settings                    # noqa: E402
from rostrum3d.mcp import estimate, render                      # noqa: E402

SCENE = '''
steel = material("m_steel", baseColor="#c9ccd1", metallic=1, roughness=0.3)
red = material("m_red", baseColor="#8c0f14", roughness=0.4, coat=1)
floor = material("m_floor", baseColor="#2a2b30", roughness=0.4)
mesh("floor", shape="plane", width=8, depth=4, material=floor)
mesh("ball", shape="sphere", radius=0.3, x=-0.8, y=0.3, material=steel).key("x", {0: -0.8, 1: 0.8}, ease="linear")
mesh("blob", shape="box", width=0.4, height=0.4, depth=0.4, bevel=0.08, y=0.25, material=red).key("ry", {0: 0, 1: 180}, ease="linear")
light("key", kind="rect", width=2, height=0.8, intensity=8, y=2.0, z=0.5).aim((0, 0, 0))
light("sky", kind="dome", color="#8a96a8", intensity=0.2)
cam = camera("cam", focalLength=40, y=0.8, z=3.0).aim((0, 0.25, 0))
shot("s", camera=cam, fps=24, start=0, end=1, width=1920, height=1080)
'''


def real_still(scene, info, s):
    t0 = time.perf_counter()
    e = Engine()
    try:
        e.ensure_scene(scene)
        frame = (s["start"] + s["end"]) // 2
        png = OUT / "still.png"
        r = e.render(camera=info["camera"], renderer="cycles", frame=frame, width=s["width"], height=s["height"], png=str(png),
                     samples=s["samples"], denoise=s["denoise"])
        assert png.is_file()
    finally:
        e.close()
    return time.perf_counter() - t0, [f["ms"] for f in r["frames"]], {}


def real_video(scene, info, s):
    pngs = OUT / "_png"
    shutil.rmtree(pngs, ignore_errors=True)
    (OUT / "v.mp4").unlink(missing_ok=True)
    pngs.mkdir()
    t0 = time.perf_counter()
    e = Engine()
    try:
        e.ensure_scene(scene)
        t_load = time.perf_counter() - t0
        r = e.render(camera=info["camera"], renderer="cycles", frames=[s["start"], s["end"]], width=s["width"], height=s["height"],
                     png=str(pngs / "v.{frame}.png"), samples=s["samples"], denoise=s["denoise"], timeoutS=3600)
    finally:
        e.close()
    t_draw = time.perf_counter() - t0
    first = min(int(p.name.split(".")[1]) for p in pngs.glob("*.png"))
    render._encode("estimate_check", pngs, "v", first, info["fps"], OUT / "v.mp4", OUT)
    total = time.perf_counter() - t0
    return total, [f["ms"] for f in r["frames"]], {"load_s": round(t_load, 2), "draw_incl_start_s": round(t_draw, 2), "encode_s": round(total - t_draw, 2)}


def main():
    scratch = OUT / "project"
    scratch.mkdir()
    (scratch / "project.json").write_text('{"items": []}', encoding="utf-8")
    doc = Document.new(KIND, str(scratch), "est")
    doc.run_script("est.py", run_source(SCENE, "est.py"))
    scene, info = describe(doc.data, "s", None), shot_info(doc.data, "s")
    rows = []
    for name, shot, still in (("still", {"renderQuality": "good"}, True),
                              ("anim full", {"renderQuality": "draft"}, False),
                              ("anim half", {"renderQuality": "draft", "renderSize": "half"}, False)):
        s = settings(shot, info)
        if still:
            s["start"] = s["end"] = (s["start"] + s["end"]) // 2
        frames = s["end"] - s["start"] + 1
        t0 = time.perf_counter()
        m = estimate_job.measure(scene, info, s)
        probe_wall = time.perf_counter() - t0
        est = estimate.scale(m, s, frames, mp4=not still)
        seen = {}                                                # the card caveat must fire while our own render runs
        spy = threading.Timer(4.0, lambda: seen.setdefault("during_render", gpu_busy.busy()))
        spy.start()
        real, ms, parts = (real_still if still else real_video)(scene, info, s)
        spy.cancel()
        parts.update(seen)
        per_real = sum(ms) / len(ms) / 1000
        rows.append({"shot": name, "frames": frames, "size": [s["width"], s["height"]], "samples": s["samples"], "estimate_s": est["seconds"],
                     "real_s": round(real, 1), "probe_wall_s": round(probe_wall, 1), "cached": m["cached"],
                     "gpu_busy": m["gpu_busy"], "error_pct": round((est["seconds"] - real) / real * 100, 1),
                     "est_per_frame_s": est["seconds_per_frame"], "real_per_frame_s": round(per_real, 3), "est_start_s": est["start_s"],
                     "est_encode_s": est["encode_s"], "real_parts": parts, "measurement": {k: v for k, v in m.items() if k != "picture"}})
        print(json.dumps({k: v for k, v in rows[-1].items() if k != "measurement"}), flush=True)
    (OUT / "estimate_check.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f'\n{"shot":10}{"frames":>7}{"size":>12}{"samples":>8}{"est s":>8}{"real s":>8}{"error %":>9}{"probe s":>9}')
    for r in rows:
        print(f'{r["shot"]:10}{r["frames"]:>7}{"x".join(map(str, r["size"])):>12}{r["samples"]:>8}{r["estimate_s"]:>8}{r["real_s"]:>8}{r["error_pct"]:>9}{"kept" if r["cached"] else r["probe_wall_s"]:>9}')


if __name__ == "__main__":
    try:
        main()
    finally:
        for p in list(OUT.glob("*.png")) + [OUT / "_png", OUT / "cache", OUT / "project", OUT / "v.mp4"]:
            shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)
