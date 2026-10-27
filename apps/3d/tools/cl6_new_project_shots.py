# CL6 pictures (3d-cl6): a new project with nothing done, Quick and Final through its own shot camera (the agent path:
# the document New makes, compiled, drawn by the engine; no window). Then one lump of clay (Clay start) at the middle,
# to see that the start frames what is made there.
#   new-project.png   Quick | Final of the empty start; Quick | Final with a 30 cm lump at the middle
# The lead runs it:  heavy.ps1 run "sam: cl6 new project" gpu <venv python> apps\3d\tools\cl6_new_project_shots.py <out>
import sys
import tempfile
from pathlib import Path

WT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(WT / "apps" / "3d" / "app"))
import main  # noqa: E402,F401  (this checkout's code and engine first)
from rostrum_core import Who  # noqa: E402
from rostrum3d.compile import describe  # noqa: E402
from rostrum3d.engine import Engine  # noqa: E402
from screen3d.files_3d import blank  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clay_paint_shots as CPS  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"C:\Users\Sam\.rostrum\waves\results\3d-cl6\pictures")
CPS.OUT = OUT
CPS.W, CPS.H = 640, 360                 # the shot's own 16:9


def look(eng):
    v, w, h, stride, _ = eng.view(camera="shot_1_camera", frame=0, width=CPS.W, height=CPS.H, renderer="storm")
    import numpy as np
    from PIL import Image
    try:
        px = np.frombuffer(v, np.uint8).reshape(h, stride)[:, :w * 4].reshape(h, w, 4).copy()
    finally:
        v.release()
    return Image.fromarray(px).convert("RGB")


def final(eng, name):
    png = OUT / f"_{name}.png"
    eng.render(camera="shot_1_camera", renderer="cycles", frame=0, width=CPS.W, height=CPS.H, samples=64, png=str(png))
    from PIL import Image
    return Image.open(png).convert("RGB")


def main_():
    OUT.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix="rostrum-cl6-new-"))
    doc = blank(folder)
    pics = []
    with Engine() as eng:
        eng.ensure_scene(describe(doc.data, "shot_1", folder))
        pics += [look(eng), final(eng, "new0")]
        doc.apply([{"op": "clay.add", "args": {"id": "lump", "at": [0, 0.15, 0], "radius": 0.15}}], Who.person())
        doc.save()
        eng.ensure_scene(describe(doc.data, "shot_1", folder))
        pics += [look(eng), final(eng, "new1")]
    CPS.strip(pics, ["New project: Quick", "New project: Final", "+ a 30 cm clay lump: Quick", "Final"],
              OUT / "new-project.png")


if __name__ == "__main__":
    main_()
