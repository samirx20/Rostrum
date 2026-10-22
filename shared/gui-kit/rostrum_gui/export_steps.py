"""Scripted steps for the Export sheet, the job chip and the Problems chip (any app; layout_run.kit_step hands them over).
The app's bridge has `exporter` (an ExportSheet) and `problems` (rows + jump; ProblemsList or the app's own).

    exportsheet open [what]|close   the sheet, open on that choice (Ctrl+E)
    exportwhere <folder>            Browse: export into this folder ("" or "default": the Renders folder; _ for spaces)
    exportnow [replace|both|cancel] press Export and wait; the answer when the file is there (none: the question stays
                                    open, for a picture); fails loudly when the export fails
    problems open|close             the Problems chip's list (after the list is worked out)
    problems-demo                   long problems in the list (for the layout check)
    job-show <percent> | job-failed <words>   the job chip as if a job ran / had failed (for the layout check)
"""
from __future__ import annotations

from PySide6.QtCore import QMetaObject, QObject
from PySide6.QtGui import QGuiApplication

WORDS = ("exportsheet", "exportwhere", "exportnow", "problems", "problems-demo", "job-show", "job-failed")
LONG_PROBLEMS = [
    {"label": "Missing font", "message": "The font “Söhne Breit Kräftig Kursiv” used by Summer launch title card isn't on "
              "this computer, so the text is drawn with a stand-in.", "fix": "Pick another font, or install it and it will be used.",
     "item": ""},
    {"label": "Missing file", "message": "C:\\Users\\Sam\\Documents\\Rostrum projects\\Summer launch film for the new "
              "headphones\\footage\\drone_take_07_final_graded.mov isn't there any more.",
     "fix": "Use Find… to look in a folder: every missing file found there is relinked in one change.", "item": "", "danger": True},
]


def _find(name: str):
    for w in QGuiApplication.topLevelWindows():
        found = w.findChild(QObject, name) if hasattr(w, "findChild") else None
        if found is not None:
            return found
    return None


def do(bridge, step: str):
    word, _, rest = step.partition(" ")
    args = rest.split()
    exp, probs = getattr(bridge, "exporter", None), getattr(bridge, "problems", None)
    if word.startswith(("export", "job")) and exp is None:
        raise RuntimeError(f"step {step!r}: {type(bridge).__name__} has no `exporter`")
    if word == "exportsheet":
        if args[1:]:
            exp.setChoice(args[1])
            if exp.choice != args[1]:
                raise RuntimeError(f"step {step!r}: no choice {args[1]!r} in {[c['value'] for c in exp.choices_list()]}")
        exp.setOpen(args[:1] == ["open"])
    elif word == "exportwhere":
        exp.setFolder("" if rest in ("", "default") else rest.replace("_", " "))
    elif word == "exportnow":
        exp.request()
        if exp.asking() and args:
            exp.answer(args[0])
        if exp.asking():
            return True
        if exp.state == "running" and not exp.wait(1800):
            raise RuntimeError(f"step {step!r}: the export did not finish in 30 minutes")
        if exp.state != "done" and not (args[:1] == ["cancel"]):
            raise RuntimeError(f"step {step!r}: {exp.note or 'nothing was exported'}")
    elif word == "problems":
        if probs is None:
            raise RuntimeError(f"step {step!r}: {type(bridge).__name__} has no `problems`")
        if not probs.rows and hasattr(probs, "wait") and not probs.wait(30):     # the first look, worked out off the GUI thread
            raise RuntimeError(f"step {step!r}: the problems list was not ready in 30 s")
        chip = _find("problemsChip")
        if chip is None:
            raise RuntimeError(f"step {step!r}: no Problems chip on screen (is the list empty?)")
        QMetaObject.invokeMethod(chip, "openList" if args[:1] == ["open"] else "closeList")
    elif word == "problems-demo":
        if hasattr(probs, "wait"):
            probs.wait(30)                       # after the app's own first look, so it doesn't replace these
        getattr(probs, "pin", probs.show_rows)(LONG_PROBLEMS)
    elif word == "job-show":
        exp._state, exp._progress = "running", float(args[0]) / 100 if args else -1.0
        exp._note = f"Exporting {exp.file_name()}"
        exp.changed.emit()
    elif word == "job-failed":
        exp._state, exp._note = "failed", "Error: export: " + rest
        exp.changed.emit()
    else:
        return False
    return True
