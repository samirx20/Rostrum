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


def make(bridge, cleaning=None) -> ProblemsList:
    """The chip. After a change it checks the song in steps of at most SLICE_S between events (diagnose.steps), so a
    whole-song check (3,352 notes moved: their times worked out again, each clip's file looked for) never holds up a
    key; a newer change drops the run and starts again from the song as it is then. The list shows once complete.
    The song's check is made once per song data: the render's and the sound's news after an edit (3-6 of them) only
    put the render's rows beside it (each started the whole check again: 9-13 runs an action, ~0.1-0.2 s)."""
    def jump(row):
        try:
            bridge.doc.item(row.get("item") or "")
        except RostrumError:
            return
        bridge.select(row["item"])
    plist = ProblemsList(jump, bridge)
    run: dict = {}
    kept: dict = {"data": None, "found": []}     # the song's own check, for the song data it was made on

    def show():
        making = cleaning.making() if cleaning else ()
        found = [_row(p) for p in kept["found"] if not (p["kind"] == "pending-take" and p["item"] in making)]
        plist.show_rows(refused_rows(bridge.soundRefused) + rows(bridge.lastRender or {}) + found)

    def start(*_):
        if pointer_quiet.busy():                     # never inside a click or a drag: a moment later
            return later.start()
        data = bridge.doc.data
        if not run.pop("again", False):
            if data is run.get("data"):              # this very song is being checked: its list comes when done
                return
            if data is kept["data"]:                 # checked already: only the render's rows follow (a render's news,
                run.clear()                          # the sound's state: 3-6 a change; an undo back to it)
                return show()
        run.clear()
        run["out"], run["data"] = [], data
        run["steps"] = steps(bridge.doc, run["out"])
        step.start()

    def recheck(*_):
        """A take made or begun (its cleaned file in the cache), or a render that may have read a missing file put
        back: the song's own rows can change with no edit, so it is checked again."""
        run["again"] = True
        later.start()

    def rendered(*_):
        stale = any(p["kind"] in ("missing-file", "pending-take") for p in kept["found"])
        recheck() if stale else later.start()

    def go():
        if "steps" not in run:
            return
        if pointer_quiet.busy():
            return later.start()
        end = time.perf_counter() + SLICE_S
        for _ in run["steps"]:
            if time.perf_counter() >= end:
                return step.start()
        kept["found"], kept["data"] = run.pop("out"), run.pop("data")
        del run["steps"]
        show()

    later = QTimer(plist, singleShot=True, interval=SETTLE_MS, timeout=start)   # once, after the edit is drawn: the
    step = QTimer(plist, singleShot=True, interval=0, timeout=go)               # chip is never what the pointer waits for
    if cleaning:                                     # (a drop ran it twice)
        cleaning.changed.connect(recheck)            # a take finished (or began): the chip follows
    bridge.renderChanged.connect(rendered)           # a render failed, or the next one worked; a file put back
    bridge.soundChanged.connect(later.start)
    bridge.docChanged.connect(later.start)       # every change (a clip added is a block: no layout news): a new song data
    kept["found"], kept["data"] = problems(bridge.doc), bridge.doc.data
    show()
    return plist
