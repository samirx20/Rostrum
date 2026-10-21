"""P-GUI-MOCK, Qt side: the same screen as gui-mock-web, built from ../gui-mock/controls.json.

    python main.py                                  # open the window
    python main.py --moment camera-dof-on --screenshot shot.png [--dump-visible visible.json]
    python main.py --record <folder>               # play demo.json "recording" in real time, save frames, quit
Any missing moment / item / control exits nonzero.
"""
import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")  # a 1600 x 960 picture means 1600 x 960 pixels

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QFontDatabase, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from demo import Player
from doc import Doc

HERE = Path(__file__).resolve().parent
MOCK = HERE.parent / "gui-mock"
UI_FONTS = ["Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI", "SF Pro Text", "Helvetica Neue"]
MONO_FONTS = ["Cascadia Mono", "Cascadia Code", "Consolas", "SF Mono", "Menlo"]


def fail(msg, code=2):
    print("FAIL:", msg, file=sys.stderr)
    sys.exit(code)


def pick(families, wanted):
    return next((f for f in wanted if f in families), QGuiApplication.font().family())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--moment")
    p.add_argument("--screenshot")
    p.add_argument("--dump-visible")
    p.add_argument("--record")
    a = p.parse_args()
    demo = json.loads((MOCK / "demo.json").read_text(encoding="utf-8"))
    if a.moment and a.moment not in demo["moments"]:
        fail(f"no moment {a.moment!r} in demo.json (have {list(demo['moments'])})")
    if (a.screenshot or a.dump_visible) and not a.moment:
        fail("--screenshot / --dump-visible need --moment")

    QQuickStyle.setStyle("Basic")
    app = QGuiApplication(sys.argv)
    families = set(QFontDatabase.families())
    doc = Doc(MOCK / "controls.json")
    engine = QQmlApplicationEngine()
    ctx = engine.rootContext()
    ctx.setContextProperty("backend", doc)
    ctx.setContextProperty("uiFont", pick(families, UI_FONTS))
    ctx.setContextProperty("monoFont", pick(families, MONO_FONTS))
    engine.load(QUrl.fromLocalFile(str(HERE / "qml" / "Main.qml")))
    if not engine.rootObjects():
        fail("QML failed to load (see errors above)", 1)
    win = engine.rootObjects()[0]
    win.resize(*demo["size"])

    code = [0]
    player = Player(app, win, doc, code)
    if a.moment:
        QTimer.singleShot(400, lambda: player.moment(demo["moments"][a.moment], a.screenshot, a.dump_visible))
    elif a.record:
        QTimer.singleShot(400, lambda: player.record(demo["recording"], Path(a.record)))
    if a.moment or a.record:  # fail loudly instead of hanging
        QTimer.singleShot(60000, lambda: (print("FAIL: timeout", file=sys.stderr), app.exit(4)))
    app.exec()
    sys.exit(code[0])


if __name__ == "__main__":
    main()
