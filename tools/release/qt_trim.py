"""Takes out of the bundled PySide6 what no Rostrum app uses: the web browser engine, 3D / charts / PDF modules,
developer tools and headers, extra control styles and translations (the screens are English for now).
The apps use QtCore, QtGui, QtQml, QtQuick, QtQuickControls2 (Basic style) and QtMultimedia; anything those need
stays. Qt stays dynamically linked and replaceable (LGPL): we only leave files out, nothing is rebuilt.
After a trim, open each app from the bundle (bundle check) — a module someone starts using must come off this list.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

UNUSED = ("WebEngine", "WebChannel", "WebSockets", "WebView", "3D", "Quick3D", "Charts", "DataVisualization", "Graphs",
          "Pdf", "Designer", "Bluetooth", "Nfc", "Sensors", "SerialPort", "SerialBus", "Scxml", "StateMachine",
          "RemoteObjects", "TextToSpeech", "VirtualKeyboard", "Location", "Positioning", "HttpServer", "SpatialAudio",
          "Help", "UiTools", "Test", "Sql", "LabsStyleKit", "QuickControls2FluentWinUI3", "QuickControls2Imagine",
          "QuickControls2Material", "QuickControls2Universal", "QuickControls2Fusion", "QuickControls2Windows")
DEV_FOLDERS = ("resources", "translations", "metatypes", "include", "typesystems", "doc", "glue", "scripts")
QML_FOLDERS = ("Qt3D", "QtQuick3D", "QtCharts", "QtDataVisualization", "QtGraphs", "QtWebEngine", "QtWebView",
               "QtWebChannel", "QtWebSockets", "QtLocation", "QtPositioning", "QtSensors", "QtTextToSpeech",
               "QtRemoteObjects", "QtScxml", "QtQuick/VirtualKeyboard", "QtQuick/Pdf", "QtQuick/Scene3D",
               "QtQuick/Scene2D", "QtQuick/Controls/Material", "QtQuick/Controls/Imagine", "QtQuick/Controls/Universal",
               "QtQuick/Controls/FluentWinUI3", "QtQuick/Controls/Fusion", "QtQuick/Controls/Windows", "QtTest",
               "Qt/labs/StyleKit")
PLUGIN_FOLDERS = ("sceneparsers", "geometryloaders", "renderers", "renderplugins", "position", "sensors",
                  "texttospeech", "webview", "sqldrivers", "designer", "canbus", "assetimporters")
NAME = re.compile(r"^(Qt6|Qt|lib)?(" + "|".join(UNUSED) + r")[A-Za-z0-9]*\.(dll|pyd|pyi)$", re.I)


def trim(pyside: Path) -> int:
    """Remove the unused parts from an installed PySide6 folder; returns the bytes saved."""
    if not (pyside / "Qt6Core.dll").is_file():
        raise SystemExit(f"FAIL: qt_trim: {pyside} is not a PySide6 folder (no Qt6Core.dll)")
    before = _size(pyside)
    for f in pyside.iterdir():
        if f.is_file() and (NAME.match(f.name) or f.suffix == ".exe"):
            f.unlink()
    for rel in DEV_FOLDERS:
        shutil.rmtree(pyside / rel, ignore_errors=True)
    for rel in QML_FOLDERS:
        shutil.rmtree(pyside / "qml" / rel, ignore_errors=True)
    for rel in PLUGIN_FOLDERS:
        shutil.rmtree(pyside / "plugins" / rel, ignore_errors=True)
    for f in (pyside / "plugins" / "platforminputcontexts").glob("*virtualkeyboard*"):
        f.unlink()
    return before - _size(pyside)


def _size(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
