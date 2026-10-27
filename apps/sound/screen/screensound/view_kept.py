"""The song's view as the person left it, kept with the song (critic r12 must-fix 2): reopened, the song shows the same
stretch of time (zoom, scroll) and each track's piano roll the same keys (the key at the view's middle, how far into
its row), so a click lands where it did before the close. Screen state, not an edit: no history, no undo, never in
the document; a song with no folder keeps it only while it is open.

    <project>/.rostrum/<item>.view-sound.json   {"time": {"start", "span", "fit", "editor"},
                                                 "rolls": {"<track id>/<kind>[/rows]": [key, into]},
                                                 "lanes": {"<track id>": [target, lane]},
                                                 "export": {"format", "rate", "trim", "stems", "markers"},
                                                 "tools": {"grid", "note", "draw", "heights", "dock"}}

`tools`: the Grid, Note ▾'s length and what Draw stamps, as the person left them (grid_slots.py): a 1/4 grid chosen
for a piano piece is still 1/4 the next day (production round: every session started with the grid menu); `heights`:
the dock's height per tool as dragged and `dock` the tool it showed (workspace.py), so the roll comes back as it was.

`lanes`: the automation lanes open under the track rows (lane_slots.openLane), put back on the song's first build.

`export`: the Export sheet's own choices as the person left them (export.py), so stems chosen and the sheet closed
without exporting are still chosen at the next open, in this window or after a restart, and cleaning the renders
folder doesn't lose them (critic r12 should-fix 2).
`editor`: the view was set while the Editor showed, so the Editor's working zoom (view_slots._editor_zoom) leaves it.
Written at most every WRITE_S while it changes (a wheel turn moves it many times), and once more when the song closes.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from PySide6.QtCore import QTimer
from rostrum_core.storage import write_atomic

WRITE_S = 0.4


def path(folder, item) -> Path:
    return Path(folder) / ".rostrum" / f"{item}.view-sound.json"


def read(folder, item) -> dict:
    """What was kept ({} when nothing, or the file can't be read: a view is never worth a refusal)."""
    if not folder or not item:
        return {}
    try:
        got = json.loads(path(folder, item).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return got if isinstance(got, dict) else {}


def lanes_of(got: dict) -> dict:
    """The open automation lanes in what was read: {track id: (target, lane)} (anything not of that shape is dropped)."""
    raw = got.get("lanes")
    return {k: (v[0], v[1]) for k, v in (raw if isinstance(raw, dict) else {}).items()
            if isinstance(v, list) and len(v) == 2 and all(isinstance(s, str) for s in v)}


class ViewKept:
    """One song's kept view: `time` and `rolls` as above, written to its file (throttled)."""

    def __init__(self, folder, item, parent=None):
        self.folder, self.item = folder, item
        got = read(folder, item)
        t, r, e, tl = got.get("time"), got.get("rolls"), got.get("export"), got.get("tools")
        self.tools: dict = tl if isinstance(tl, dict) else {}
        self.lanes: dict = lanes_of(got)
        self.time: dict = t if isinstance(t, dict) else {}
        self.export: dict = e if isinstance(e, dict) else {}
        self.rolls: dict = {k: v for k, v in (r if isinstance(r, dict) else {}).items()
                            if isinstance(v, list) and len(v) == 2}
        self._last = 0.0
        self._timer = QTimer(parent)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.write)

    def keep_time(self, start: float, span: float, fit: bool, editor: bool):
        now = {"start": round(start, 4), "span": round(span, 4), "fit": bool(fit), "editor": bool(editor)}
        if now != self.time:
            self.time = now
            self._later()

    def keep_roll(self, shown: str, key: int, into: float):
        now = [int(key), round(float(into), 2)]
        if self.rolls.get(shown) != now:
            self.rolls[shown] = now
            self._later()

    def keep_lanes(self, open_lanes: dict):
        now = {k: list(v) for k, v in open_lanes.items()}
        if now != {k: list(v) for k, v in self.lanes.items()}:
            self.lanes = {k: tuple(v) for k, v in now.items()}
            self._later()

    def keep_export(self, choices: dict):
        if choices != self.export:
            self.export = dict(choices)
            self._later()

    def keep_tools(self, tools: dict):
        """`tools`' entries over the kept ones (each keeper writes only its own)."""
        now = {**self.tools, **tools}
        if now != self.tools:
            self.tools = now
            self._later()

    def _later(self):
        if not self.folder or self._timer.isActive():
            return
        wait = self._last + WRITE_S - time.monotonic()
        if wait <= 0:
            self.write()
        else:
            self._timer.start(int(wait * 1000) + 1)

    def flush(self):
        """A write still waiting is made now (the song closes, the app quits)."""
        try:
            waiting = self._timer.isActive()
        except RuntimeError:          # the song was closed and freed already (its timer went with it): nothing waits
            return
        if waiting:
            self.write()

    def write(self):
        """Now (the song closes, or the throttle's wait ran out)."""
        self._timer.stop()
        if not self.folder or not self.item:
            return
        self._last = time.monotonic()
        try:
            write_atomic(path(self.folder, self.item), json.dumps({"time": self.time, "rolls": self.rolls,
                                                                    **({"lanes": self.lanes} if self.lanes else {}),
                                                                    **({"export": self.export} if self.export else {}),
                                                                    **({"tools": self.tools} if self.tools else {})}))
        except OSError:
            pass            # a read-only project still works; its view just isn't kept
