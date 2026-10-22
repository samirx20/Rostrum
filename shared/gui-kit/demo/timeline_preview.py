"""Look harness and layout check for the timeline kit (TimelineHeader, Ruler, HScroll, timeview), long texts included.

    python shared/gui-kit/demo/timeline_preview.py [out folder]      # every state at the four sizes: <out>/*.png,
                                                                     # faults.txt; nonzero exit on any fault
States: whole (fit), zoomed (the view scrolled in, the scroll bar shown), naming (M's name field with Shared open),
compact (⊟ folded). Each runs in its own process (layout_run.run_all).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_gui import layout_run, start  # noqa: E402
from rostrum_gui.timeview import TimeView, TimeViewObject  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = r"C:\Users\Sam\.rostrum\waves\results\kit\s35\timeline"
STATES = [("whole", [], []), ("zoomed", [], ["zoom"]), ("naming", [], ["zoom", "name"]), ("compact", [], ["fold"])]


def main():
    a = argparse.ArgumentParser()
    a.add_argument("out", nargs="?", default=OUT)
    a.add_argument("--step", action="append", default=[])
    a.add_argument("--check-layout")
    a.add_argument("--check-name")
    args = a.parse_args()
    if not args.check_name:
        sys.exit(layout_run.run_all(Path(__file__), STATES, args.check_layout or args.out))

    view = TimeViewObject(TimeView(20.0))
    app, engine, win = start(HERE / "qml" / "TimelinePreview.qml", {"timeView": view}, layout_run.SIZES[0])
    for s in args.step:
        if s == "zoom":
            view.zoomAt(2.5, 0.4)
        elif s == "name":
            win.metaObject().invokeMethod(win, "name")
        elif s == "fold":
            win.setProperty("compact", True)
        else:
            raise SystemExit(f"unknown step {s!r}")
    layout_run.sweep(app, win, args.check_layout, args.check_name, lambda: True)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
