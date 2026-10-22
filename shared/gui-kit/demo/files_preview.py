"""Look harness and layout check for S36's files pieces on the kit, long texts included: the start screen's "Open the
last version that works" banner, the "Fit · 50 % ▾" view control with its menu, the marker right-click menu, and the ≡
menu with its repair rows (Find missing files…, Open the last version that works).

    python shared/gui-kit/demo/files_preview.py [out folder]     # every state at the four sizes; nonzero exit on a fault
States: rescue (start screen with the banner), view (control + its menu open), marker (a flag's menu open), menu (≡ open).
Each runs in its own process (layout_run.run_all). Everything here is made in a scratch folder.
"""
import argparse
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document, Who, toy  # noqa: E402
from rostrum_gui import layout_run, start  # noqa: E402
from rostrum_gui.canvasview import CanvasView  # noqa: E402
from rostrum_gui.docfiles import AppFiles  # noqa: E402
from rostrum_gui.markers import MarkerWatch  # noqa: E402
from rostrum_gui.project_files import ProjectFiles  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = r"C:\Users\Sam\.rostrum\waves\results\kit\s36\files"
STATES = [("rescue", [], ["rescue"]), ("view", [], ["view"]), ("marker", [], ["marker"]), ("menu", [], ["menu"])]
KIND = toy.KIND


class Host:
    bridge = None

    def show(self, doc):
        self.shown = doc


def damaged_project(root: Path) -> Path:
    """A project whose last step is cut off and whose document file is broken."""
    doc = toy.sample(root / "A very long project name that is likely to be cut off somewhere on screen", "main")
    doc.save()
    for layer, name in (("title", "One"), ("card", "Two"), ("cam_1", "Three")):
        doc.apply({"op": "layer.rename", "target": [layer], "args": {"name": name}}, Who.person("sam"))
        doc.save()
    hist = Path(doc.folder) / ".rostrum" / "main.history.jsonl"
    lines = hist.read_text(encoding="utf-8").splitlines()
    hist.write_text("\n".join(lines[:-1] + [lines[-1][:30]]) + "\n", encoding="utf-8")
    (Path(doc.folder) / "docs" / f"main{KIND.ext}").write_text("{ broken", encoding="utf-8")
    return Path(doc.folder)


def make_files(root: Path) -> ProjectFiles:
    def blank(folder):
        doc = toy.sample(folder, "main") if folder else Document.new(KIND)
        if folder:
            doc.save()
        return doc
    kind = AppFiles(app="test", title="Rostrum2D", noun="project", ext=KIND.ext, untitled="Untitled", folder=lambda: root,
                    blank=blank, open=lambda f, i: Document.open(f, i, KIND), resolve=lambda p: (Path(p), "main"),
                    doc_kind=KIND, refs=lambda d: [("title", "name", str(root / "old" / "a-clip-with-a-long-name.mov"))],
                    ref_op=lambda d, i: "layer.rename")
    return ProjectFiles(kind, Host())


def main():
    a = argparse.ArgumentParser()
    a.add_argument("out", nargs="?", default=OUT)
    a.add_argument("--step", action="append", default=[])
    a.add_argument("--check-layout")
    a.add_argument("--check-name")
    args = a.parse_args()
    if not args.check_name:
        sys.exit(layout_run.run_all(Path(__file__), STATES, args.check_layout or args.out))

    root = Path(tempfile.mkdtemp(prefix="rostrum-files-preview-", dir=r"C:\Users\Sam\.rostrum\waves\scratch\sam-s36-files"))
    os.environ["ROSTRUM_PROJECTS_DIR"] = str(root)
    files = make_files(root)
    view = CanvasView()
    view.setViewSize(900, 500)
    view.setContent(0, 0, 1920, 1080)
    view.job("fit_all")
    markers = MarkerWatch(root, owner="2d")
    for t in (2.0, 5.5):
        markers.add(t)
    markers.rename(markers.rows()[0]["id"], "Logo lands on the beat with a very long name")
    bad = damaged_project(root)
    if "rescue" in args.step:
        from rostrum_gui import docfiles
        docfiles.remember(files.kind, bad, "main", bad.name)        # the last project, but damaged
        files.launch()                                      # refused: the start screen with the banner
    else:
        files.launch(files.kind.blank(root / "Promo").folder)
        if "menu" in args.step:
            try:
                files.openPath(str(bad))
            except Exception:  # noqa: BLE001  the refusal is the point: it offers the rebuild
                pass
            files.setStart(False)
    app, engine, win = start(HERE / "qml" / "FilesPreview.qml", {"files": files, "view": view, "markerWatch": markers, "markerRows": markers.rows()},
                             layout_run.SIZES[0])
    for s in args.step:
        if s in ("view", "marker", "menu"):
            win.setProperty("open", s)
    layout_run.sweep(app, win, args.check_layout, args.check_name, lambda: True)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
