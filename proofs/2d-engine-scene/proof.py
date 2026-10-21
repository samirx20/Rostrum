"""H6 proof: the same scenes drawn by the Python stopgap evaluator and by the engine's own (Rust) evaluator, side by
side, with timings. Runs rostrum2d with the proposed engine.py change (engine.py.patch) from a scratch copy.

    .venv\\Scripts\\python.exe proofs\\2d-engine-scene\\proof.py <patched rostrum2d parent dir> <scratch> <results dir>
"""
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from PIL import Image, ImageChops, ImageDraw  # noqa: E402
from rostrum_core import Document  # noqa: E402
from rostrum2d import KIND, run_source  # noqa: E402
from rostrum2d import engine as E  # noqa: E402
from rostrum2d.scene import describe, frame_at  # noqa: E402
from rostrum2d import stopgap_html  # noqa: E402

assert "evaluator: str = \"engine\"" in Path(E.__file__).read_text(encoding="utf-8"), f"not the patched handle: {E.__file__}"
HERE = Path(__file__).resolve().parent
EXE = HERE.parents[1] / "apps" / "2d" / "engine" / "target" / "agent" / "rostrum2d-render.exe"
SHOTS = {"meridian": (Path(r"C:\Users\Sam\.rostrum\waves\results\stage2\2d\agent\title.py"), [0.4, 0.83, 1.43, 2.9]),
         "pro-shot": (HERE / "pro_shot.py", [0.5, 1.2, 2.0, 2.9])}


def scene_of(script: Path, scratch: Path) -> dict:
    doc = Document.new(KIND, folder=scratch / f"{script.stem}-project", item="shot")
    doc.run_script(script.name, run_source(script.read_text(encoding="utf-8"), script.name))
    return describe(doc.data)


def rgba_frame(eng, req: dict):
    """A frame as raw RGBA (what the live canvas will ask for): (reply, round-trip ms)."""
    t0 = time.perf_counter()
    eng.proc.stdin.write((json.dumps({"frame": req}) + "\n").encode())
    eng.proc.stdin.flush()
    rep = json.loads(eng.proc.stdout.readline())
    if "error" in rep:
        raise E.EngineError(rep["error"])
    eng.proc.stdout.read(rep["bytes"])
    return rep, (time.perf_counter() - t0) * 1000


def scrub(eng, scene, evaluator: str, times: list[float]) -> dict:
    """Round trip per frame, and the engine's own split, over a list of times."""
    rows = []
    for t in times:
        if evaluator == "engine":
            rep, ms = rgba_frame(eng, {"t": t, "rgba": True})
        else:
            eng._open()
            t0 = time.perf_counter()
            stage = stopgap_html.stage(frame_at(scene, t), eng.caps)
            py = (time.perf_counter() - t0) * 1000
            rep, ms = rgba_frame(eng, {"stage": stage, "rgba": True})
            rep["timing"]["evalMs"] = py
            ms += py
        rows.append({"ms": ms, **{k: rep["timing"].get(k, 0) for k in ("evalMs", "diffMs", "layoutMs", "paintMs", "edits")}})
    med = lambda k: round(sorted(r[k] for r in rows)[len(rows) // 2], 2)  # noqa: E731
    return {"frames": len(rows), "medianMs": med("ms"), "maxMs": round(max(r["ms"] for r in rows), 1),
            "median": {k: med(k) for k in ("evalMs", "diffMs", "layoutMs", "paintMs", "edits")}}


def compare(a: Path, b: Path) -> dict:
    ia, ib = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    d = ImageChops.difference(ia, ib)
    hist = d.convert("L").histogram()
    n = ia.width * ia.height
    return {"maxDiff": max(i for i, c in enumerate(hist) if c), "pixelsOver2": sum(hist[3:]), "share": sum(hist[3:]) / n}


def sheet(rows, out: Path):
    """Rows of [stopgap | engine | difference ×8], each 640 px wide."""
    w, h, pad, top = 640, 360, 8, 34
    img = Image.new("RGB", (3 * w + 4 * pad, len(rows) * (h + top) + pad), "#202024")
    dr = ImageDraw.Draw(img)
    for r, (t, a, b) in enumerate(rows):
        ia, ib = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
        diff = ImageChops.difference(ia, ib).point(lambda v: min(255, v * 8))
        y = pad + r * (h + top)
        for c, (im, label) in enumerate([(ia, f"Python stopgap  t={t}s"), (ib, f"Rust engine  t={t}s"), (diff, "difference x8")]):
            x = pad + c * (w + pad)
            dr.text((x, y + 4), label, fill="#e0e0e8")
            img.paste(im.resize((w, h), Image.LANCZOS), (x, y + top - 8))
    img.save(out)


def main(scratch: Path, results: Path):
    scratch.mkdir(parents=True, exist_ok=True)
    results.mkdir(parents=True, exist_ok=True)
    report = {}
    for name, (script, stills) in SHOTS.items():
        scene = scene_of(script, scratch)
        p = scene["comp"]["props"]
        fps, n = p["fps"], round(p["duration"] * p["fps"])
        r = report[name] = {"size": f'{p["width"]}x{p["height"]}', "fps": fps, "frames": n}
        pngs = {}
        for ev in ("python", "engine"):
            with E.Engine(EXE, evaluator=ev) as eng:
                t0 = time.perf_counter()
                eng.load(scene)
                r[f"{ev}LoadMs"] = round((time.perf_counter() - t0) * 1000, 1)
                for t in stills:
                    png = scratch / f"{name}-{t:.2f}s-{ev}.png"
                    eng.still(t, png)
                    pngs[(t, ev)] = png
                t0 = time.perf_counter()
                vid = eng.video(results / f"{name}-{ev}-evaluator.mp4")
                r[f"{ev}ExportS"] = round(time.perf_counter() - t0, 2)
                r[f"{ev}ExportMsPerFrame"] = round((time.perf_counter() - t0) * 1000 / vid["frames"], 1)
                # Scrubbing: frame after frame forward, then random jumps (the playhead dragged and dropped).
                fwd = [i / fps for i in range(n)]
                jumps = [random.Random(i).uniform(0, p["duration"]) for i in range(60)]
                r[f"{ev}ScrubForward"] = scrub(eng, scene, ev, fwd)
                r[f"{ev}ScrubJumps"] = scrub(eng, scene, ev, jumps)
                if ev == "engine":
                    # A small edit (a drag): one layer moved, the same frame drawn again.
                    lid = scene["comp"]["layers"][-1]["id"]
                    t_mid = stills[1]
                    rgba_frame(eng, {"t": t_mid, "rgba": True})
                    ms = []
                    for k in range(30):
                        t0 = time.perf_counter()
                        eng._request({"edit": [{"id": lid, "props": {"x": 960 + k * 4}}]})
                        rep, _ = rgba_frame(eng, {"t": t_mid, "rgba": True})
                        ms.append((time.perf_counter() - t0) * 1000)
                    r["engineEditRepaint"] = {"layer": lid, "medianMs": round(sorted(ms)[15], 2),
                                              "edits": rep["timing"]["edits"], "paintMs": round(rep["timing"]["paintMs"], 2)}
        r["stills"] = {f"{t}": compare(pngs[(t, "python")], pngs[(t, "engine")]) for t in stills}
        sheet([(t, pngs[(t, "python")], pngs[(t, "engine")]) for t in stills], results / f"{name}-python-vs-rust-evaluator.png")
        for t in stills:
            Image.open(pngs[(t, "engine")]).save(results / f"{name}-{t:.2f}s-rust-evaluator.png")
    (results / "timings.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main(Path(sys.argv[2]), Path(sys.argv[3]))
