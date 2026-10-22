"""Scripted steps for the file actions (steps.py hands these over). Each calls what the File menu calls; one that
fails raises, so a scripted run exits nonzero.

    new [name] | save | saveas <name> | openproject <doc file or project folder> | autosave (write the recovery copy now)
    restore | discard (answer the recovery question) | filemenu open|close | askclose (press the window's close button)
    about (Help › About and licences) | help (the Help menu, open) | guide <file.md> (Help › that guide)
Names: _ for spaces.
"""
from __future__ import annotations

from PySide6.QtCore import Q_ARG, QMetaObject

from rostrum_gui import guides

WORDS = ("new", "save", "saveas", "openproject", "autosave", "restore", "discard", "filemenu", "askclose", "about", "help", "guide")


def do_file_step(bridge, win, word, rest, step):
    files = bridge.files
    arg = " ".join(rest).replace("_", " ")
    if word == "filemenu":
        QMetaObject.invokeMethod(win, "setFileMenuOpen", Q_ARG("QVariant", rest[0] == "open"))
        return
    if word in ("about", "help"):
        QMetaObject.invokeMethod(win, "openAbout" if word == "about" else "openHelp")
        return
    if word == "guide":
        guides.open_named(win, rest[0])
        return
    if word == "askclose":
        QMetaObject.invokeMethod(win, "askClose")
        return
    if word == "discard":
        files.discard()
        return
    ok = {"new": lambda: files.newProject(arg), "save": files.save, "saveas": lambda: files.saveAs(arg),
          "openproject": lambda: files.openPath(" ".join(rest)), "autosave": files.autosave,
          "restore": files.restore}[word]()
    if not ok:
        raise RuntimeError(f"step {step!r}: {files.host.bridge.status}")
    print(f"{word}: {files.label} ({files.doc.folder})")
