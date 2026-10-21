"""P-GUI proof: one Qt Quick window (PySide6) with panels, inspector, timeline, Ctrl+K command bar,
a live OpenGL viewport and 1080p video playback.

    python main.py [--video <mp4>] [--mode viewport|video]
    python main.py --measure 20 --mode viewport|video [--churn] --out result.json
    python main.py --screenshot shot.png [--mode viewport|video] [--size 1600x960]
"""
import argparse
import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6 import QtMultimedia  # noqa: F401  registers QVideoSink for videoSink lookup
from PySide6.QtGui import QFontDatabase, QGuiApplication, QSurfaceFormat
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterType
from PySide6.QtQuick import QQuickWindow, QSGRendererInterface
from PySide6.QtQuickControls2 import QQuickStyle

from measure import Measurer, Stats, screenshot_later
from viewport import GLViewport

HERE = Path(__file__).resolve().parent
DEFAULT_VIDEO = Path(r"C:\Users\Sam\.rostrum\waves\scratch\sam-S1\test_1080p60.mp4")
# First installed family wins. Segoe UI Variable ships with Windows 11; Segoe UI with every Windows; SF on Mac.
UI_FONTS = ["Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI", "SF Pro Text", "Helvetica Neue"]
MONO_FONTS = ["Cascadia Mono", "Cascadia Code", "Consolas", "SF Mono", "Menlo"]


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--video", type=Path, default=DEFAULT_VIDEO)
    p.add_argument("--mode", choices=["viewport", "video"], default="viewport")
    p.add_argument("--measure", type=float, help="record for this many seconds, write --out, quit")
    p.add_argument("--churn", action="store_true", help="while measuring, switch selection and resize the window")
    p.add_argument("--out", default="measure.json")
    p.add_argument("--screenshot", help="grab the window to this PNG after 2 s and quit")
    p.add_argument("--size", default="1600x960")
    p.add_argument("--open-commands", action="store_true", help="open the command bar at start (for a screenshot)")
    p.add_argument("--threaded", action="store_true", help="Qt's threaded render loop (see README: can deadlock here)")
    p.add_argument("--vsync", action="store_true", help="swap interval 1 (see README: throttles a covered window)")
    p.add_argument("--on-top", action="store_true", help="keep the window above others (Windows slows covered windows)")
    a = p.parse_args()
    if not a.video.exists():
        sys.exit(f"video not found: {a.video} (make one with ffmpeg, see README)")
    return a


def pick(families, wanted):
    return next((f for f in wanted if f in families), QGuiApplication.font().family())


def main():
    args = parse_args()
    # Force the OpenGL backend: the viewport draws raw GL on Qt's context (the usdview / Hydra Storm path).
    QQuickWindow.setGraphicsApi(QSGRendererInterface.OpenGL)
    # The viewport here draws in Python, so the render thread needs Python's lock; any GUI-thread Python call that
    # waits on the render thread (resize, grab, QTest.qWait) then deadlocks. One-thread loop unless --threaded.
    # (A native C++ Hydra viewport never takes the Python lock, so the real apps can use the threaded loop.)
    os.environ["QSG_RENDER_LOOP"] = "threaded" if args.threaded else "basic"
    fmt = QSurfaceFormat.defaultFormat()
    # Swap interval 0 by default: with vsync on, unattended runs here crawled at ~4-6 fps on both GPUs (screen off?)
    # (pure QML too). With 0, Qt's render loop paces itself at the display rate and DWM composites (no tearing).
    fmt.setSwapInterval(1 if args.vsync else 0)
    QSurfaceFormat.setDefaultFormat(fmt)
    QQuickStyle.setStyle("Basic")
    os.environ.setdefault("QT_MEDIA_BACKEND", "ffmpeg")  # Qt 6 default on Windows; stated for the record

    app = QGuiApplication(sys.argv)
    app.setApplicationName("Rostrum GUI proof")
    families = set(QFontDatabase.families())
    qmlRegisterType(GLViewport, "Rostrum", 1, 0, "GLViewport")

    engine = QQmlApplicationEngine()
    ctx = engine.rootContext()
    ctx.setContextProperty("uiFont", pick(families, UI_FONTS))
    ctx.setContextProperty("monoFont", pick(families, MONO_FONTS))
    ctx.setContextProperty("videoUrl", QUrl.fromLocalFile(str(args.video)))
    ctx.setContextProperty("startMode", args.mode)
    ctx.setContextProperty("openCommandsAtStart", args.open_commands)
    ctx.setContextProperty("startSize", [int(v) for v in args.size.split("x")])
    stats = Stats()
    ctx.setContextProperty("stats", stats)
    engine.load(QUrl.fromLocalFile(str(HERE / "qml" / "Main.qml")))
    if not engine.rootObjects():
        sys.exit("QML failed to load (see errors above)")
    win = engine.rootObjects()[0]
    engine.exit.connect(app.exit)  # Qt.exit() from QML

    if args.on_top:
        win.setFlag(Qt.WindowStaysOnTopHint, True)
        win.raise_()
        win.requestActivate()
    stats.attach(win)
    video_out = win.findChild(object, "videoOut")
    video_out.property("videoSink").videoFrameChanged.connect(stats.on_video_frame)
    viewport = win.findChild(GLViewport, "viewport")
    print(f"font: {pick(families, UI_FONTS)} / {pick(families, MONO_FONTS)}; "
          f"graphics: {win.rendererInterface().graphicsApi()}; video: {args.video}")

    keep = None
    if args.measure:
        keep = Measurer(app, win, win, stats, viewport, args)
    elif args.screenshot:
        win.setProperty("viewMode", args.mode)
        screenshot_later(app, win, args.screenshot, args.threaded)
    if args.measure or args.screenshot:  # fail loudly instead of hanging
        limit = int(((args.measure or 0) + 15) * 1000)
        QTimer.singleShot(limit, lambda: (print(f"TIMEOUT after {limit} ms", file=sys.stderr), app.exit(4)))
    code = app.exec()
    del keep
    sys.exit(code)


if __name__ == "__main__":
    main()
