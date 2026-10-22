"""Takes out of the bundled PySide6 what no Rostrum app uses: the web browser engine, 3D / charts / PDF modules,
developer tools and headers, extra control styles and translations (the screens are English for now).
The apps use QtCore, QtGui, QtQml, QtQuick, QtQuickControls2 (Basic style) and QtMultimedia; anything those need
stays. Qt stays dynamically linked and replaceable (LGPL): we only leave files out, nothing is rebuilt.
The apps' scripted steps (the release walk, agents driving the screen) use QtTest, so it stays too.
A module the shipped code imports is never trimmed: `trim` reads every `PySide6.Qt…` import under apps/ and shared/
and stops the build if this list would take one out (0.1.3-dev's trial lost QtTest and 2D could not start).
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

UNUSED = ("WebEngine", "WebChannel", "WebSockets", "WebView", "3D", "Quick3D", "Charts", "DataVisualization", "Graphs",
          "Pdf", "Designer", "Bluetooth", "Nfc", "Sensors", "SerialPort", "SerialBus", "Scxml", "StateMachine",
          "RemoteObjects", "TextToSpeech", "VirtualKeyboard", "Location", "Positioning", "HttpServer", "SpatialAudio",
          "Help", "UiTools", "Sql", "LabsStyleKit", "QuickControls2FluentWinUI3", "QuickControls2Imagine",
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
IMPORT = re.compile(r"PySide6\.(Qt\w+)|from\s+PySide6\s+import\s+\(?([\w\s,]+)")
NOT_SHIPPED = {"tests", "demo", "build", ".venv", "target", "__pycache__"}


QML_IMPORT = re.compile(r"^\s*import\s+(Qt[\w.]*)", re.M)


def _shipped(repo: Path, pattern: str):
    for top in ("apps", "shared"):
        for f in (repo / top).rglob(pattern):
            if not NOT_SHIPPED.intersection(f.relative_to(repo).parts):
                yield f, f.read_text(encoding="utf-8", errors="replace")


def imported(repo: Path) -> dict[str, Path]:
    """Every PySide6 module the shipped Python under apps/ and shared/ imports -> one file that imports it."""
    found = {}
    for f, text in _shipped(repo, "*.py"):
        for m in IMPORT.finditer(text):
            for name in [m.group(1)] if m.group(1) else re.findall(r"Qt\w+", m.group(2)):
                found.setdefault(name, f)
    return found


def qml_imported(repo: Path) -> dict[str, Path]:
    """Every Qt QML module the shipped .qml files import, as its folder under PySide6\\qml (QtQuick/Controls)."""
    found = {}
    for f, text in _shipped(repo, "*.qml"):
        for m in QML_IMPORT.finditer(text):
            found.setdefault(m.group(1).replace(".", "/"), f)
    return found


def clashes(repo: Path) -> dict[str, Path]:
    """What the shipped code imports that this trim would take out."""
    out = {n: f for n, f in imported(repo).items() if NAME.match(f"{n}.pyd")}
    out.update({n: f for n, f in qml_imported(repo).items() if any(n == r or n.startswith(r + "/") for r in QML_FOLDERS)})
    return out


def trim(pyside: Path, repo: Path) -> int:
    """Remove the unused parts from an installed PySide6 folder; returns the bytes saved. Stops (loudly) when a
    module the apps import would be removed."""
    if not (pyside / "Qt6Core.dll").is_file():
        raise SystemExit(f"FAIL: qt_trim: {pyside} is not a PySide6 folder (no Qt6Core.dll)")
    clash = clashes(repo)
    if clash:
        raise SystemExit("FAIL: qt_trim would remove Qt modules the apps import: "
                         + "; ".join(f"{n} ({f.relative_to(repo)})" for n, f in sorted(clash.items()))
                         + ". Take them off UNUSED / QML_FOLDERS in tools/release/qt_trim.py.")
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
