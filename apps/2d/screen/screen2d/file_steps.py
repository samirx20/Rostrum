"""Scripted steps for the file actions (steps.py hands these over). Each calls what the ≡ menu calls (the kit's
ProjectFiles, `bridge.files`); one that fails raises, so a scripted run exits nonzero.

    new [name] | openproject <doc file or project folder> | startscreen open|close | version [name] (Save a version; the
    time when no name) | duplicateproject <name> (a copy in the projects folder; the window stays;
    `duplicate` alone is the layer step) | filemenu open|close | scenemenu open|new|<scene id>
    about (Help › About and licences) | report (Help › Report a problem) | agents [agent id] (Help › Connect an AI agent; with an id, its by-hand text open) | help (the Help menu, open) | guide <file.md> (Help › that guide)
Names: _ for spaces.
"""
from __future__ import annotations

from PySide6.QtCore import Q_ARG, QMetaObject

from rostrum_gui import guides

WORDS = ("new", "openproject", "startscreen", "version", "duplicateproject", "filemenu", "scenemenu", "about", "report", "agents", "help", "guide")


def do_file_step(bridge, win, word, rest, step):
    files = bridge.files
    arg = " ".join(rest).replace("_", " ")
    if word == "scenemenu":                                 # scenemenu open|new|<scene id> (the crumb, scenes.py)
        if rest[0] == "open":
            QMetaObject.invokeMethod(win, "openSceneMenu")
        else:
            bridge.showScene("+scene" if rest[0] == "new" else rest[0])
        return
    if word == "filemenu":
        QMetaObject.invokeMethod(win, "setFileMenuOpen", Q_ARG("QVariant", rest[0] == "open"))
        return
    if word in ("about", "help", "report"):
        QMetaObject.invokeMethod(win, {"about": "openAbout", "help": "openHelp", "report": "openReport"}[word])
        return
    if word == "agents":
        QMetaObject.invokeMethod(win, "openConnectAgent", Q_ARG("QVariant", rest[0] if rest else ""))
        return
    if word == "guide":
        guides.open_named(win, rest[0])
        return
    if word == "startscreen":
        files.setStart(rest[0] == "open")
        return
    ok = {"new": lambda: files.newProject(arg), "openproject": lambda: files.openPath(" ".join(rest)),
          "version": lambda: files.saveVersion(arg), "duplicateproject": lambda: files.duplicate(arg)}[word]()
    if not ok:
        raise RuntimeError(f"step {step!r}: {files.host.bridge.status}")
    print(f"{word}: {files.name} ({files.doc.folder})")
