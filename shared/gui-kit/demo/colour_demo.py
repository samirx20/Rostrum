"""Look harness for the kit's colour pickers (ColorPicker, PaintPicker, PaintField, ColorField).

    python shared/gui-kit/demo/colour_demo.py [--kind solid|linear] [--shot out.png]
Opens a 1646x900 window with a fill field and the fill picker open beside it; with --shot saves the window and quits."""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from PySide6.QtCore import QMetaObject, QTimer  # noqa: E402

from rostrum_gui import start
from rostrum_gui.app import stop  # noqa: E402
from rostrum_gui.colour_bank import ColourBank  # noqa: E402

FILLS = {
    "solid": {"type": "solid", "color": "#ff3d7f"},
    "linear": {"type": "linear", "angle": 90, "color": "#ff7a45", "stops": [
        {"at": 0, "color": "#ff7a45", "opacity": 1}, {"at": 0.55, "color": "#ff3d7f", "opacity": 1},
        {"at": 1, "color": "#8a4cff", "opacity": 0.8}]},
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", default="linear", choices=FILLS)
    ap.add_argument("--shot")
    args = ap.parse_args()
    bank = ColourBank()
    bank.set_project(["#0b1020", "#1b2347", "#4c8dff", "#ff7a45", "#ff3d7f", "#8a4cff", "#f2b33d", "#ffffff"])
    bank.set_brand("Northwind", ["#111827", "#ffe11a", "#e8501e", "#f4efe6"])
    app, engine, win = start(HERE / "qml" / "ColourDemo.qml", {"colourBank": bank}, size=(1646, 900))
    win.setProperty("fill", FILLS[args.kind])
    QTimer.singleShot(300, lambda: QMetaObject.invokeMethod(win, "openFill"))

    def shoot():
        img = win.grabWindow()
        if img.isNull() or not img.save(args.shot):
            raise RuntimeError(f"could not save {args.shot}")
        print(f"saved {args.shot}")
        app.quit()
    if args.shot:
        QTimer.singleShot(1000, shoot)
    app.exec()
    stop(engine, win)


main()
