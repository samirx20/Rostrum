"""Starting a Rostrum window: one Qt app, the RostrumKit import path, the fonts, the bridge as `backend`."""
from __future__ import annotations

import os
import sys
from pathlib import Path

KIT_QML = Path(__file__).resolve().parent.parent / "qml"     # holds the RostrumKit module
UI_FONTS = ["Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI", "SF Pro Text", "Helvetica Neue"]
MONO_FONTS = ["Cascadia Mono", "Cascadia Code", "Consolas", "SF Mono", "Menlo"]


def start(main_qml: Path, context: dict, size=(1600, 960), providers: dict | None = None, imports=()):
    """Make the app and load main_qml with `context` as context properties (plus uiFont / monoFont),
    `providers` as image providers ({"frame": provider} -> image://frame/...) and extra QML import folders.
    Returns (app, engine, window). Fails loudly when the QML does not load."""
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")   # a 1600 x 960 screenshot is 1600 x 960 pixels
    from PySide6.QtGui import QFontDatabase, QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuickControls2 import QQuickStyle
    from PySide6.QtCore import QUrl

    QQuickStyle.setStyle("Basic")      # we draw every control ourselves; Basic is only the Popup base
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
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
    from rostrum_gui.notices import Notices, app_id   # the Help → About and licences screen (every app has one)
    ctx.setContextProperty("notices", Notices(app_id(main_qml), engine))
    if app_id(main_qml) in ("2d", "sound"):           # Help → Connect an AI agent (apps with an agent server to add)
        from rostrum_gui.agents import Agents
        ctx.setContextProperty("agents", Agents(app_id(main_qml), engine))
    from rostrum_gui.guides import GuidePages        # Help → a guide, read by the kit's guide viewer
    ctx.setContextProperty("guidePages", GuidePages(engine))
    for k, v in context.items():
        ctx.setContextProperty(k, v)
    engine.load(QUrl.fromLocalFile(str(main_qml)))
    if not engine.rootObjects():
        raise RuntimeError(f"QML failed to load: {main_qml} (errors above)")
    win = engine.rootObjects()[0]
    win.resize(*size)
    return app, engine, win


def stop(engine, win=None):
    """Close a window started by `start`: the window and its engine go first, now, then the caller releases what their
    bindings read (the bridge, its parts, image providers). The other way round, every binding still alive re-reads a
    context object that is already gone ("Cannot read property … of null"). Every app closes its windows through this."""
    import shiboken6
    if win is not None:
        win.close()
    if engine is not None and shiboken6.isValid(engine):
        shiboken6.delete(engine)                   # destroys the window and every binding with it


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
