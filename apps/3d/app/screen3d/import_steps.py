"""Scripted steps for imports (steps.py hands these on; importing.py):

    import-hover <x> <y> (the landing ring a file dragged from Explorer shows, at viewport px; no real drag)
    import-note <import id> (what follows an import of a file in another unit: the status line's message once, and
    Keep original size in the selection's panel; the import must have been read through the engine)
    import-file <path> (the Import group's dialog answered with this file: lands in the middle of the view)
    import-drop <path> <x> <y> (the file dropped on the viewport at viewport px)
"""
from __future__ import annotations

from PySide6.QtCore import Q_ARG, QMetaObject, QObject, QUrl

WORDS = ("import-hover", "import-note", "import-file", "import-drop")


def do(bridge, win, step: str):
    word, *rest = step.split()
    if word == "import-hover":
        drop = win.findChild(QObject, "importDrop")
        if drop is None:
            raise RuntimeError("import-hover: the viewport's file drop area is not there")
        QMetaObject.invokeMethod(drop, "hoverAt", Q_ARG("QVariant", float(rest[0])), Q_ARG("QVariant", float(rest[1])))
    elif word == "import-note":
        bridge.select(rest[0])
        bridge.importer._tell(rest[0])
        if not bridge.importer.keepFor:
            raise RuntimeError(f"import-note: {rest[0]} was not rescaled (no unit message to show)")
    elif word == "import-file":
        bridge.importer.importAtCentre(QUrl.fromLocalFile(rest[0]).toString())
    elif word == "import-drop":
        dpr = win.devicePixelRatio()
        bridge.importer.dropAt([QUrl.fromLocalFile(rest[0])], float(rest[1]) * dpr, float(rest[2]) * dpr)
    else:
        raise ValueError(f"unknown step {step!r}")
