"""Sound's Problems list (the kit's ProblemsChip, rostrum_gui/problems.py): what is wrong with the song now, in words with
what to do: the same list inspect_diagnose gives agents (rostrum_sound/diagnose.py: missing files, files outside the song,
cleaned takes not made yet, sounds no longer made), the newest render's refusal while it stands (a note its sound can't
play: the track to jump to) and the newest render's loudest peak over full scale (clipping, red).
"""
from __future__ import annotations

import time

from PySide6.QtCore import QTimer
from rostrum_core import RostrumError
from rostrum_gui import pointer_quiet
from rostrum_gui.problems import ProblemsList
from rostrum_sound.diagnose import LABELS, problems, steps

from .select_slots import SETTLE_MS
from .strips import MASTER


def rows(render: dict) -> list[dict]:
    peak = render.get("truePeak")
    if not isinstance(peak, (int, float)) or peak <= 0:
        return []
    return [{"label": "Clipping", "danger": True, "item": MASTER,
             "message": f"The mix goes over full scale: its loudest peak is +{peak:.1f} dBTP, so it will crackle.",
             "fix": "Turn the master or the loudest track down, or turn on the master's limiter."}]


SLICE_S = 0.004      # the most one step of the check holds the screen's thread; the next waits for the loop's next turn


def _row(p: dict) -> dict:
    return {**p, "label": LABELS[p["kind"]], "danger": p["kind"] == "missing-file"}


def refused_rows(refused: dict) -> list[dict]:
    """The newest render's refusal (bridge.soundRefused) as a row: red, with the track it names. Its message already says
    what to do (plain_errors.say), so no second fix line repeats it."""
    if not refused:
        return []
    kind = refused["kind"]
    return [{"label": LABELS.get(kind, "Can't make the sound"), "danger": True, "item": refused["item"],
             "message": refused["message"], "fix": ""}]


def doc_rows(doc, making=frozenset()) -> list[dict]:
    """The song's problems; a cleaned take that is being made now is activity (the Clean up bar shows it), not a problem."""
    return [_row(p) for p in problems(doc) if not (p["kind"] == "pending-take" and p["item"] in making)]


def make(bridge, cleaning=None) -> ProblemsList:
    """The chip. After a change it checks the song in steps of at most SLICE_S between events (diagnose.steps), so a
    whole-song check (3,352 notes moved: their times worked out again, each clip's file looked for) never holds up a
    key; a newer change drops the run and starts again from the song as it is then. The list shows once complete."""
    def jump(row):
        try:
            bridge.doc.item(row.get("item") or "")
        except RostrumError:
            return
        bridge.select(row["item"])
    plist = ProblemsList(jump, bridge)
    run: dict = {}

    def start(*_):
        if pointer_quiet.busy():                     # never inside a click or a drag: a moment later
            return later.start()
        run["out"] = []
        run["steps"] = steps(bridge.doc, run["out"])
        step.start()

    def go():
        if "steps" not in run:
            return
        if pointer_quiet.busy():
            return later.start()
        end = time.perf_counter() + SLICE_S
        for _ in run["steps"]:
            if time.perf_counter() >= end:
                return step.start()
        making = cleaning.making() if cleaning else ()
        found = [_row(p) for p in run.pop("out") if not (p["kind"] == "pending-take" and p["item"] in making)]
        del run["steps"]
        plist.show_rows(refused_rows(bridge.soundRefused) + rows(bridge.lastRender or {}) + found)

    later = QTimer(plist, singleShot=True, interval=SETTLE_MS, timeout=start)   # once, after the edit is drawn: the
    step = QTimer(plist, singleShot=True, interval=0, timeout=go)               # chip is never what the pointer waits for
    if cleaning:                                     # (a drop ran it twice)
        cleaning.changed.connect(later.start)        # a take finished (or began): the chip follows
    bridge.renderChanged.connect(later.start)
    bridge.soundChanged.connect(later.start)     # a render failed, or the next one worked
    bridge.docChanged.connect(later.start)       # every change (a clip added is a block: no layout news)
    plist.show_rows(refused_rows(bridge.soundRefused) + rows(bridge.lastRender or {}) + doc_rows(bridge.doc, cleaning.making() if cleaning else ()))
    return plist
