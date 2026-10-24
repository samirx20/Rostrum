"""Sound's Problems list (the kit's ProblemsChip, rostrum_gui/problems.py): what is wrong with the song now, in words with
what to do: the same list inspect_diagnose gives agents (rostrum_sound/diagnose.py: missing files, files outside the song,
cleaned takes not made yet, sounds no longer made) and the newest render's loudest peak over full scale (clipping, red).
"""
from __future__ import annotations

from PySide6.QtCore import QTimer
from rostrum_core import RostrumError
from rostrum_gui.problems import ProblemsList
from rostrum_sound.diagnose import problems

from .select_slots import SETTLE_MS
from .strips import MASTER


def rows(render: dict) -> list[dict]:
    peak = render.get("truePeak")
    if not isinstance(peak, (int, float)) or peak <= 0:
        return []
    return [{"label": "Clipping", "danger": True, "item": MASTER,
             "message": f"The mix goes over full scale: its loudest peak is +{peak:.1f} dBTP, so it will crackle.",
             "fix": "Turn the master or the loudest track down, or turn on the master's limiter."}]


WORDS = {"missing-file": "Missing file", "outside-project": "File outside the song", "pending-take": "Cleaned take not made",
         "no-longer-made": "No longer made"}


def doc_rows(doc, making=frozenset()) -> list[dict]:
    """The song's problems; a cleaned take that is being made now is activity (the Clean up bar shows it), not a problem."""
    return [{**p, "label": WORDS[p["kind"]], "danger": p["kind"] == "missing-file"} for p in problems(doc)
            if not (p["kind"] == "pending-take" and p["item"] in making)]


def make(bridge, cleaning=None) -> ProblemsList:
    def jump(row):
        try:
            bridge.doc.item(row.get("item") or "")
        except RostrumError:
            return
        bridge.select(row["item"])
    plist = ProblemsList(jump, bridge)
    def show(*_):
        plist.show_rows(rows(bridge.lastRender or {}) + doc_rows(bridge.doc, cleaning.making() if cleaning else ()))
    later = QTimer(plist, singleShot=True, interval=SETTLE_MS, timeout=show)   # once, after the edit is drawn: the
    if cleaning:                                     # chip is never what the pointer waits for (a drop ran it twice)
        cleaning.changed.connect(later.start)        # a take finished (or began): the chip follows
    bridge.renderChanged.connect(later.start)
    bridge.timelineChanged.connect(later.start)
    show()
    return plist
