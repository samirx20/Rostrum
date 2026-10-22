"""Sound's Problems list (the kit's ProblemsChip, rostrum_gui/problems.py): what is wrong with the song now, in words with
what to do. Today one source: the newest render's loudest peak over full scale (clipping, red). Missing files and
missing models are said where they happen (the clip, the model question) and are not listed here yet.
"""
from __future__ import annotations

from rostrum_core import RostrumError
from rostrum_gui.problems import ProblemsList

from .strips import MASTER


def rows(render: dict) -> list[dict]:
    peak = render.get("truePeak")
    if not isinstance(peak, (int, float)) or peak <= 0:
        return []
    return [{"label": "Clipping", "danger": True, "item": MASTER,
             "message": f"The mix goes over full scale: its loudest peak is +{peak:.1f} dBTP, so it will crackle.",
             "fix": "Turn the master or the loudest track down, or turn on the master's limiter."}]


def make(bridge) -> ProblemsList:
    def jump(row):
        try:
            bridge.doc.item(row.get("item") or "")
        except RostrumError:
            return
        bridge.select(row["item"])
    plist = ProblemsList(jump, bridge)
    bridge.renderChanged.connect(lambda *_: plist.show_rows(rows(bridge.lastRender or {})))
    return plist
