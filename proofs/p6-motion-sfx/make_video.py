"""Build the slides document from slides.py, save its JSON + motion facts, and (with --render) render the silent video.

    python make_video.py            # document + slides-doc.json + slides-motion.json only
    python make_video.py --render   # also renders slides-silent.mp4 (a GPU job: run it through heavy.ps1)
"""
import json
import os
import shutil
import sys
from pathlib import Path

os.environ.setdefault("ROSTRUM2D_ENGINE", r"C:\Users\Sam\.rostrum\waves\scratch\priyam-P6-lead\rostrum2d-render.exe")

import rostrum2d
from rostrum2d.engine import Engine
from rostrum2d.mcp.motion import analyse
from rostrum2d.scene import describe
from rostrum_core import Document

HERE = Path(__file__).parent
SCRATCH = Path(r"C:\Users\Sam\.rostrum\waves\scratch\priyam-P6-slides")
RESULTS = Path(r"C:\Users\Sam\.rostrum\waves\results\stage2\sound-motion")


def build() -> dict:
    folder = SCRATCH / "doc"
    if folder.exists():
        shutil.rmtree(folder)
    doc = Document.new(rostrum2d.KIND, folder=str(folder), item="slides")
    source = (HERE / "slides.py").read_text(encoding="utf-8")
    doc.run_script("slides.py", rostrum2d.run_source(source, "slides.py"))
    return doc.data


def main() -> None:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    data = build()
    (SCRATCH / "slides-doc.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
    comp = data["comps"][0]
    (SCRATCH / "slides-motion.json").write_text(json.dumps(analyse(comp), indent=1), encoding="utf-8")
    print("document + motion facts saved in", SCRATCH)
    if "--render" in sys.argv:
        RESULTS.mkdir(parents=True, exist_ok=True)
        with Engine() as eng:
            eng.load(describe(data))
            for t in (0.36, 1.4, 3.0, 3.6, 5.6, 7.5):
                eng.still(t, SCRATCH / f"frame_{t:.2f}.png")
            out = RESULTS / "slides-silent.mp4"
            eng.video(out)
        if not out.exists() or out.stat().st_size == 0:
            raise SystemExit(f"render failed: {out} missing or empty")
        print("rendered", out)


if __name__ == "__main__":
    main()
