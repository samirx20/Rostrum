# Export resume walk (critic 3d-final items 3 and 4): the render sheet's MP4, "Frame x of N" while a shot renders, a Cancel
# that keeps the finished frames, and Render again continuing from them. Real input on visible controls in a background
# window (never focused); bridge state is only read. A tiny shot: 320×180, Cycles 8 samples, 12 frames.
#   heavy.ps1 run "<team>: export resume walk" gpu <venv python> apps\3d\tools\export_resume_walk.py --out <folder>
# Pictures and export_resume_walk.json go to --out. Exit 0 = every check passed.
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("ROSTRUM_BACKGROUND_WINDOWS", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import clay_walk as W  # noqa: E402  (puts this checkout's code first; its real-input helpers)
import clay_paint_walk as CP  # noqa: E402

from rostrum_core import Document  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from rostrum_gui.app import qt_app  # noqa: E402

import main as app3d  # noqa: E402

SRC = '''
cam = camera("cam", focalLength=35, z=3, y=0.6).aim((0, 0.2, 0))
light("key", kind="distant", intensity=3)
mesh("floor", shape="plane", sx=4, sz=4)
ball = mesh("ball", shape="sphere", radius=0.3, y=0.3)
ball.key("x", {0: -0.6, 1: 0.6})
shot("hero", name="Hero 01", camera=cam, fps=10, start=0, end=1.2, width=320, height=180,
     renderQuality="custom", renderSamples=8, renderDenoise=True)
'''
OUT: Path = Path(".")
REPORT: dict = {"checks": [], "notes": [], "pictures": {}}


def chk(ok, line):
    REPORT["checks"].append({"ok": bool(ok), "line": line})
    print(("PASS " if ok else "FAIL ") + line, flush=True)


def snap(win, name):
    W.pump(0.4)
    p = OUT / f"{name}.png"
    win.grabWindow().save(str(p))
    REPORT["pictures"][name] = str(p)


def click_text(win, text):
    it = CP.find_text(win.contentItem(), text)
    chk(it is not None, f"'{text}' is on screen")
    if it is not None:
        W.click(win, it)
        W.pump(0.4)
    return it


def watch(ex, seconds, until):
    """Pump until `until()`, keeping every running note the sheet showed."""
    end = time.perf_counter() + seconds
    while not until() and time.perf_counter() < end:
        W.pump(0.05)
        if ex.note and (not REPORT["notes"] or REPORT["notes"][-1] != ex.note):
            REPORT["notes"].append(ex.note)
    return until()


def main():
    global OUT
    a = argparse.ArgumentParser()
    a.add_argument("--out", default=r"C:\Users\Sam\.rostrum\waves\results\3d-critic-fixes\B")
    OUT = Path(a.parse_args().out)
    OUT.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="rostrum-resumewalk-", dir=os.environ.get("ROSTRUM_SCRATCH")))
    app = qt_app()  # noqa: F841
    doc = Document.new(KIND, folder=project, item="scene")
    doc.run_script("scene.py", run_source(SRC, "scene.py"))
    doc.save()
    screen = app3d.Screen((1646, 900))
    try:
        screen.show(doc, autosave=True)
        win, b = screen.win, screen.bridge
        ex = b.exporter
        W.pump(60, screen.ready, "the first picture")
        more = W.find(win.contentItem(), "renderMore")
        chk(more is not None and more.isVisible(), "the ▾ beside Render is on screen")
        W.click(win, more)
        W.pump(5, lambda: ex.open, "the render sheet")
        click_text(win, "Hero 01 · 12 frames")
        chk(ex._choice == "shot", "the shot's frames are picked")
        snap(win, "1-sheet-pictures")
        click_text(win, "Hero 01 · MP4 video")
        chk(ex._choice == "video", f"MP4 video is picked ({ex._choice})")
        chk(CP.find_text(win.contentItem(), "Save as") is None, "Save as is gone for an MP4")
        snap(win, "2-sheet-mp4")

        click_text(win, "Render 12 frames as MP4")
        watch(ex, 120, lambda: ex._done_frames >= 1 or ex.state in ("done", "failed"))
        snap(win, "3-running")
        chk(any(n.startswith("Frame ") and n.endswith(" of 12") for n in REPORT["notes"]), "the note counted 'Frame x of 12'")
        click_text(win, "Cancel")
        watch(ex, 60, lambda: ex.state in ("cancelled", "done", "failed"))
        kept = ex._done_frames
        REPORT["keptAtStop"] = kept
        chk(ex.state == "cancelled" and 0 < kept < 12, f"stopped part way ({ex.state}, {kept} frames)")
        chk(ex.note.startswith(f"Stopped · {kept} finished frame"), f"the sheet says the frames are kept: {ex.note!r}")
        part = sorted((project / "renders" / "scene").glob("v*.partial"))
        pngs = sorted(part[0].glob("_png/*.png")) if part else []
        REPORT["keptFiles"] = len(pngs)
        chk(len(pngs) >= kept > 0, f"{len(pngs)} finished frames are on disk in {part[0] if part else '(no folder)'}")
        snap(win, "4-stopped")
        W.pump(5, lambda: ex.resumeLine != "", "the continue line")
        chk(ex.resumeLine == f"Continues from {len(pngs)} finished frames", f"the sheet says {ex.resumeLine!r}")
        chk(CP.find_text(win.contentItem(), ex.resumeLine) is not None, "that line is on screen")
        snap(win, "5-continues")

        REPORT["notes"].append("--- again ---")
        click_text(win, "Render 12 frames as MP4")
        watch(ex, 180, lambda: ex.state in ("done", "failed", "cancelled"))
        again = REPORT["notes"][REPORT["notes"].index("--- again ---") + 1:]
        first = next((n for n in again if n.startswith("Frame ")), "")
        chk(first == f"Frame {len(pngs) + 1} of 12 · continues from {len(pngs)} finished frames",
            f"it went on from frame {len(pngs) + 1}: {first!r}")
        chk(ex.state == "done", f"the MP4 is made ({ex.state}: {ex.note})")
        snap(win, "6-done")
        files = [Path(f) for f in ex._result.get("files", [])]
        mp4 = next((f for f in files if f.name.endswith(".mp4") and not f.name.endswith("-share.mp4")), None)
        share = next((f for f in files if f.name.endswith("-share.mp4")), None)
        chk(mp4 is not None and mp4.is_file() and share is not None and share.is_file(), f"the mp4 and its share copy: {files}")
        if mp4 is not None and mp4.is_file():
            n = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                                "stream=nb_read_frames,width,height", "-of", "json", str(mp4)], capture_output=True, text=True).stdout
            REPORT["ffprobe"] = json.loads(n or "{}")
            st = (REPORT["ffprobe"].get("streams") or [{}])[0]
            chk(st.get("nb_read_frames") == "12" and st.get("width") == 320, f"the mp4 has 12 frames at 320 wide ({st})")
            shutil.copyfile(mp4, OUT / mp4.name)
            shutil.copyfile(share, OUT / share.name)
        chk(not list((project / "renders" / "scene").glob("*.partial")), "no half-made folder is left")
    finally:
        screen.close() if hasattr(screen, "close") else None
        (OUT / "export_resume_walk.json").write_text(json.dumps(REPORT, indent=1), encoding="utf-8")
        shutil.rmtree(project, ignore_errors=True)
    bad = [c for c in REPORT["checks"] if not c["ok"]]
    print(f"{len(REPORT['checks']) - len(bad)} of {len(REPORT['checks'])} checks passed", flush=True)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
