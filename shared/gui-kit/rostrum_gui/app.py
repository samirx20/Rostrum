"""Starting a Rostrum window: one Qt app, the RostrumKit import path, the fonts, the bridge as `backend`."""
from __future__ import annotations

import os
import sys
from pathlib import Path

KIT_QML = Path(__file__).resolve().parent.parent / "qml"     # holds the RostrumKit module
UI_FONTS = ["Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI", "SF Pro Text", "Helvetica Neue"]
MONO_FONTS = ["Cascadia Mono", "Cascadia Code", "Consolas", "SF Mono", "Menlo"]


def start(main_qml: Path, context: dict, size=(1600, 960)):
    """Make the app and load main_qml with `context` as context properties (plus uiFont / monoFont).
    Returns (app, engine, window). Fails loudly when the QML does not load."""
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")   # a 1600 x 960 screenshot is 1600 x 960 pixels
    from PySide6.QtGui import QFontDatabase, QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuickControls2 import QQuickStyle
    from PySide6.QtCore import QUrl

    QQuickStyle.setStyle("Basic")      # we draw every control ourselves; Basic is only the Popup base
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    families = set(QFontDatabase.families())
    pick = lambda wanted: next((f for f in wanted if f in families), QGuiApplication.font().family())  # noqa: E731
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(KIT_QML))
    ctx = engine.rootContext()
    ctx.setContextProperty("uiFont", pick(UI_FONTS))
    ctx.setContextProperty("monoFont", pick(MONO_FONTS))
    for k, v in context.items():
        ctx.setContextProperty(k, v)
    engine.load(QUrl.fromLocalFile(str(main_qml)))
    if not engine.rootObjects():
        raise RuntimeError(f"QML failed to load: {main_qml} (errors above)")
    win = engine.rootObjects()[0]
    win.resize(*size)
    return app, engine, win
