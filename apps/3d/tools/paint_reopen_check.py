# Paint reopen check (brief 20): the walk's lid unfolded by the real core (xatlas), a roughness scuff painted where the
# shot camera's pick says the lid's top is (its `uv`), saved in a scratch project, opened again, rendered in Cycles;
# then the stroke undone (one step) and rendered again. Through the lock (GPU):
#   heavy.ps1 run "<team>: paint reopen check" gpu <venv python> apps\3d\tools\paint_reopen_check.py <out folder>
# Saves reopened-final.png and undone-final.png (1646×900) and prints what it checked.
import sys
import tempfile
from pathlib import Path

WT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(WT / "apps" / "3d" / "python"), str(WT / "shared" / "core"), str(WT / "shared" / "painting-kit")]
from rostrum_core import Document, Who                       # noqa: E402
from rostrum3d import KIND, ops_mesh, run_source             # noqa: E402
from rostrum3d.compile import describe                       # noqa: E402
from rostrum3d.engine import Engine                          # noqa: E402

SAM, W, H = Who.person(), 1646, 900
SCENE = (Path(__file__).with_name("paint_lid_scene.py")).read_text(encoding="utf-8")


def render(eng, doc, png):
    eng.load(describe(doc.data, "hero", doc.folder))
    eng.render(camera="cam", renderer="cycles", frame=0, width=W, height=H, samples=128, denoise=True, png=str(png))


if __name__ == "__main__":
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="rostrum-paint-"))
    doc = Document.new(KIND, folder=project, item="scene")
    doc.run_script("s.py", run_source(SCENE, "s.py"))
    with Engine() as eng:
        ops_mesh.use_engine(eng, project)
        doc.apply({"op": "mesh.unfold", "target": ["lid"]}, SAM)
        print("unfolded:", len(doc.item("lid")["uvs"]) // 2, "corners")
        eng.load(describe(doc.data, "hero", project))
        pts = []
        for k in range(12):                                   # a short arc across the lid's top, picked like a drag
            hit = eng.pick(camera="cam", frame=0, width=W, height=H, x=W * (0.42 + 0.015 * k), y=H * (0.47 + 0.004 * k * k / 3))
            if hit.get("hit") and hit.get("item") == "lid" and hit.get("uv"):
                u, v = hit["uv"]
                pts.append([round(u * 2048, 2), round((1 - v) * 2048, 2), 1.0])
        print("picked on the lid:", len(pts), "of 12; first uv point", pts[:1])
        assert len(pts) >= 6, "the pick gave too few uv points on the lid"
        doc.apply([{"op": "paint.add", "target": ["lid"], "args": {"id": "scuffs", "name": "Scuffs", "channel": "roughness"}}], SAM)
        doc.apply([{"op": "stroke.add", "target": ["scuffs"], "args": {"points": pts, "color": "#c8c8c8", "size": 70,
                                                                       "brush": "chalk", "opacity": 0.8}}], SAM, label="Paint on Lid")
        doc.save()
        again = Document.open(project, "scene", KIND)
        assert again.item("scuffs")["strokes"] == doc.item("scuffs")["strokes"] and again.item("lid")["uvs"] == doc.item("lid")["uvs"]
        print("reopened: layer, stroke and uvs the same")
        render(eng, again, out / "reopened-final.png")
        again.undo(SAM)
        assert again.item("scuffs")["strokes"] == [], "one undo should take the whole stroke"
        print("one undo: the stroke is gone, the layer stays")
        render(eng, again, out / "undone-final.png")
        ops_mesh.use_engine(None)
    print("pictures in", out)
