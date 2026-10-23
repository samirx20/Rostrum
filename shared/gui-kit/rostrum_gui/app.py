"""Starting a Rostrum window: one Qt app, the RostrumKit import path, the fonts, the bridge as `backend`."""
from __future__ import annotations

import os
import sys
from pathlib import Path

KIT_QML = Path(__file__).resolve().parent.parent / "qml"     # holds the RostrumKit module
UI_FONTS = ["Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI", "SF Pro Text", "Helvetica Neue"]
_styled = False                                              # the Quick Controls style is set (once, before any QML)
MONO_FONTS = ["Cascadia Mono", "Cascadia Code", "Consolas", "SF Mono", "Menlo"]


def offscreen_env() -> dict:
    """The environment of a window that draws offscreen (the layout check's runs and every picture or step run)."""
    return {"QT_QPA_PLATFORM": "offscreen", **({"QT_QPA_FONTDIR": "C:/Windows/Fonts"} if os.name == "nt" else {})}


def qt_app():
    """The one Qt app. A run that takes pictures or clicks by script (--shot / --step / --check-layout) draws offscreen:
    a real window draws only while the screen is on (Windows stops drawing it on a locked or sleeping screen), and a
    run on one froze every animation and clicked a layout that was never redrawn (H53: the onion switch showed off
    while on, its click missed). QT_QPA_PLATFORM set by hand wins (a run meant to be watched)."""
    from PySide6.QtGui import QGuiApplication
    from rostrum_core import userhome
    from rostrum_core.userhome import FLAGS
    userhome.screen_opened()                       # a screen nobody launched by main.py is a scripted run (never the person's settings)
    if QGuiApplication.instance() is None and any(a.split("=", 1)[0] in FLAGS for a in sys.argv[1:]):
        for k, v in offscreen_env().items():
            os.environ.setdefault(k, v)
    return QGuiApplication.instance() or QGuiApplication(sys.argv)


def start(main_qml: Path, context: dict, size=(1600, 960), providers: dict | None = None, imports=()):
    """Make the app and load main_qml with `context` as context properties (plus uiFont / monoFont),
    `providers` as image providers ({"frame": provider} -> image://frame/...) and extra QML import folders.
    Returns (app, engine, window). Fails loudly when the QML does not load."""
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")   # a 1600 x 960 screenshot is 1600 x 960 pixels
    from PySide6.QtGui import QFontDatabase, QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuickControls2 import QQuickStyle
    from PySide6.QtCore import QUrl

    from . import qt_faults
    qt_faults.watch()                  # Qt's "not supported" warnings fail a scripted run (qt_faults.py)
    global _styled
    if not _styled:                    # once per process, before the first engine: a second window must not set it
        QQuickStyle.setStyle("Basic")  # we draw every control ourselves; Basic is only the Popup base
        _styled = True
    app = qt_app()
    from rostrum_gui.notices import NAMES, app_id
    from .qml_cache import name_app
    if not app.organizationName():                      # unnamed ("python"): its own compiled-QML cache, capped (qml_cache.py)
        name_app(app, NAMES.get(app_id(main_qml), "Rostrum"))
    link_in_accent(app)
    families = set(QFontDatabase.families())
    pick = lambda wanted: next((f for f in wanted if f in families), QGuiApplication.font().family())  # noqa: E731
    engine = QQmlApplicationEngine()
    engine.warnings.connect(lambda ws: [print(f"QML: {w.toString()}", file=sys.stderr) for w in ws])   # never silent
    engine.addImportPath(str(KIT_QML))
    for folder in imports:
        engine.addImportPath(str(folder))
    for name, provider in (providers or {}).items():
        engine.addImageProvider(name, provider)
    ctx = engine.rootContext()
    ctx.setContextProperty("uiFont", pick(UI_FONTS))
    ctx.setContextProperty("monoFont", pick(MONO_FONTS))
    from rostrum_gui.notices import Notices           # the Help → About and licences screen (every app has one)
    ctx.setContextProperty("notices", Notices(app_id(main_qml), engine))
    if app_id(main_qml) in ("2d", "sound"):           # Help → Connect an AI agent (apps with an agent server to add)
        from rostrum_gui.agents import Agents
        ctx.setContextProperty("agents", Agents(app_id(main_qml), engine))
    from rostrum_gui.keymap import KeyMap            # the shared keys: the key list and hover help when an app has no hub
    ctx.setContextProperty("sharedKeys", KeyMap("Rostrum").entries())
    from rostrum_gui.guides import GuidePages        # Help → a guide, read by the kit's guide viewer
    ctx.setContextProperty("guidePages", GuidePages(engine))
    from rostrum_gui.panel_sizes import PanelSizes   # the panel sizes a person dragged (AppShell's frame layout)
    ctx.setContextProperty("panelSizes", PanelSizes(app_id(main_qml), engine))
    from rostrum_gui.colour_bank import bank         # every colour picker's swatches and eyedropper (colour_bank.py)
    ctx.setContextProperty("colourBank", bank())
    for k, v in context.items():
        ctx.setContextProperty(k, v)
    engine.load(QUrl.fromLocalFile(str(main_qml)))
    if not engine.rootObjects():
        raise RuntimeError(f"QML failed to load: {main_qml} (errors above)")
    win = engine.rootObjects()[0]
    win.resize(*size)
    from rostrum_gui.focus_areas import watch         # the area last pressed takes the keys (AppShell.pressedAt)
    watch(win)
    return app, engine, win


def stop(engine, win=None, then=None):
    """Close a window started by `start`: the window and its engine go first, then `then()` releases what their
    bindings read (the bridge, its parts, image providers). The other way round, every binding still alive re-reads a
    context object that is already gone ("Cannot read property … of null"). Every app closes its windows through this.
    While the event loop runs (a click opened another project) the window hides now and the deleting waits for the next
    turn of the loop: the click's own QML handler may still be running, and deleting its item under it is not
    supported (the start screen's New, H43). At quit (the loop has ended) everything goes at once."""
    import shiboken6
    from PySide6.QtCore import QCoreApplication, QTimer
    if win is not None:
        win.close()

    def finish():
        if engine is not None and shiboken6.isValid(engine):
            shiboken6.delete(engine)               # destroys the window and every binding with it
        if then is not None:
            then()
    app = QCoreApplication.instance()
    if app is not None and app.thread().loopLevel() > 0:
        QTimer.singleShot(0, finish)
    else:
        finish()


def link_in_accent(app):
    """Links in a guide (Markdown text) take the application palette's link colour, not the Text's linkColor, so the
    palette gets Theme.qml's accent (read from there: one place for the colour). Qt's default is a dark blue."""
    import re
    from PySide6.QtGui import QColor, QPalette
    theme = (KIT_QML / "RostrumKit" / "Theme.qml").read_text(encoding="utf-8")
    accent = re.search(r'property color accent:\s*"(#[0-9a-fA-F]+)"', theme)
    pal = app.palette()
    pal.setColor(QPalette.Link, QColor(accent.group(1)))
    app.setPalette(pal)
