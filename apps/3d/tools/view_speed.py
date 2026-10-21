# Quick view speed (H20): how many live viewport pictures a second the engine hands the screen, end to end (the `view`
# request, the shared-memory read and the QImage copy the screen makes), orbiting the free camera round the sample
# scene so nothing is reused. Also saves the shot camera's picture at each size, for a before / after difference.
# Through the lock:
#   heavy.ps1 run "<team>: view speed" gpu <worktree>\.venv\Scripts\python.exe apps\3d\tools\view_speed.py <out folder> [label] [field=value ...]
#   ... view_speed.py --diff <folder a> <folder b> <out folder>     (difference pictures, x16, and the largest step)
import json, math, sys, time
from pathlib import Path

WT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(WT / "apps" / "3d" / "python"), str(WT / "apps" / "3d" / "app"), str(WT / "shared" / "core"),
                str(WT / "shared" / "gui-kit")]
import numpy as np                                           # noqa: E402
from PIL import Image                                        # noqa: E402
from PySide6.QtGui import QImage                             # noqa: E402

SIZES = [(960, 540), (1280, 720), (1600, 900)]
FRAMES = 60


def scene():
    from rostrum_core import Document
    from rostrum3d import KIND, run_source
    from rostrum3d.compile import describe
    from screen3d.sample import SOURCE
    doc = Document.new(KIND)
    doc.run_script("sample.py", run_source(SOURCE, "sample.py"))
    return describe(doc.data, "hero")


def grab(eng, req):
    view, w, h, stride, reply = eng.view(**req)
    try:
        img = QImage(view, w, h, stride, QImage.Format.Format_RGBA8888).copy()   # what the screen does
    finally:
        view.release()
    return img, reply


def to_array(img: QImage) -> np.ndarray:
    return np.frombuffer(img.constBits(), np.uint8, img.sizeInBytes()).reshape(img.height(), img.bytesPerLine())[
        :, :img.width() * 4].reshape(img.height(), img.width(), 4).copy()


def measure(out: Path, label: str, extra: dict):
    from rostrum3d.engine import Engine
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    with Engine() as eng:
        eng.load(scene())
        for w, h in SIZES:
            base = {"frame": 0, "width": w, "height": h, "renderer": "storm", "selected": ["ball"], **extra}
            img, _ = grab(eng, {**base, "camera": "cam"})
            Image.fromarray(to_array(img)).save(out / f"shot-{w}x{h}.png")
            for i in range(5):                                # warm up
                grab(eng, {**base, "eye": [3 * math.sin(i / 10), 1.2, 3 * math.cos(i / 10)], "target": [0, .3, 0], "fov": 40})
            draw, core, t0 = [], [], time.perf_counter()
            for i in range(FRAMES):
                a = i / FRAMES * 2 * math.pi
                _, r = grab(eng, {**base, "eye": [3 * math.sin(a), 1.2, 3 * math.cos(a)], "target": [0, .3, 0], "fov": 40})
                draw.append(r["timing"]["drawMs"])
                core.append(r["timing"]["totalMs"])
            wall = time.perf_counter() - t0
            rows.append({"size": f"{w}x{h}", "fps": round(FRAMES / wall, 1), "msPerPicture": round(wall / FRAMES * 1000, 1),
                         "coreDrawMs": round(float(np.median(draw)), 1), "coreTotalMs": round(float(np.median(core)), 1)})
            print(rows[-1], flush=True)
        gpu = eng.info().get("gpu")
    lines = [f"Quick view speed, {label}: {FRAMES} pictures orbiting the sample scene, one item selected, GPU {gpu}",
             "size        pictures/s   ms each   (engine: drawing ms, whole request ms; medians)"]
    lines += [f"{r['size']:<11} {r['fps']:>10}   {r['msPerPicture']:>7}   ({r['coreDrawMs']}, {r['coreTotalMs']})" for r in rows]
    (out / "viewport-fps.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "viewport-fps.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")


def diff(a: Path, b: Path, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    worst = 0
    for pa in sorted(a.glob("shot-*.png")):
        x = np.asarray(Image.open(pa).convert("RGB"), np.int16)
        y = np.asarray(Image.open(b / pa.name).convert("RGB"), np.int16)
        d = np.abs(x - y)
        worst = max(worst, int(d.max()))
        Image.fromarray(np.clip(d * 16, 0, 255).astype(np.uint8)).save(out / f"diff-x16-{pa.name}")
        print(f"{pa.name}: largest step {d.max()} of 255, mean {d.mean():.3f}, pixels off by >2: {(d.max(-1) > 2).mean():.4%}")
    return worst


if __name__ == "__main__":
    if sys.argv[1] == "--diff":
        diff(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
    else:
        measure(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else "",
                {k: json.loads(v) for k, v in (kv.split("=", 1) for kv in sys.argv[3:])})
