"""Look harness for the open-if-changed groups option: a 3D-style light (groups_demo.py) in the kit Inspector.

    python shared/gui-kit/demo/groups_preview.py [out folder]        # every state at the four sizes: <out>/*.png,
                                                                     # faults.txt; nonzero exit on any fault
States: light (Light and Position open, "Spread · Card · Lights only · Shadow" as names), opened (a name clicked: its
group opens in place), changed (Spread set away from its default: it opens by itself).
Steps: click <objectName> | set <param> <json>. Each state runs in its own process (layout_run.run_all).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from PySide6.QtCore import QTimer  # noqa: E402

import groups_demo  # noqa: E402
from panel_preview import do  # noqa: E402
from rostrum_gui import layout_run, start  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = r"C:\Users\Sam\.rostrum\waves\results\kit\k3\groups"
STATES = [
    ("light", [], []),
    ("opened", [], ["click fold:Card"]),
    ("changed", [], ["set spread 90"]),
]


def main():
    a = argparse.ArgumentParser()
    a.add_argument("out", nargs="?", default=OUT)
    a.add_argument("--step", action="append", default=[])
    a.add_argument("--check-layout")
    a.add_argument("--check-name")
    args = a.parse_args()
    if not args.check_name:
        sys.exit(layout_run.run_all(Path(__file__), STATES, args.check_layout or args.out))
    bridge = groups_demo.Bridge(groups_demo.sample())
    bridge.select("key")
    app, engine, win = start(HERE / "qml" / "GroupsPreview.qml", {"backend": bridge}, layout_run.SIZES[0])

    def run():
        try:
            for s in args.step:
                do(bridge, None, win, s)
            if bridge.status.startswith("Error"):
                raise RuntimeError(bridge.status)
        except Exception as e:  # noqa: BLE001  a step that fails fails the state, loudly
            print(f"FAIL: {e}", file=sys.stderr)
            return app.exit(3)
        QTimer.singleShot(400, lambda: layout_run.sweep(app, win, args.check_layout, args.check_name, lambda: True))
    QTimer.singleShot(500, run)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
