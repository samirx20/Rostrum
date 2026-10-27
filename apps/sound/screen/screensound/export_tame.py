"""The Export sheet's "Tame the peaks first" (ExportSettings.qml): reaching a streaming target on music with real
dynamics needs a lot of limiting, which flattens the climax. Lifting the quiet parts does not help there (the loudness
meter leaves out passages more than 10 LU under the loud ones), taming the peaks does: a gentle compressor on the
peakiest track takes its sharpest attacks off, its makeup keeps the track where it sat, and the master then needs far
less limiting (fit_peaks.py; a solo piano 9.8 -> 3.8 dB). The search renders the song several times, so it runs on its
own engine on a worker; the edit lands as one undo step on the song, the compressor in plain sight in the track's chain."""
from __future__ import annotations

import copy
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QObject, Signal
from rostrum_sound import compile as compile_doc
from rostrum_sound import fit_loudness as fit
from rostrum_sound.trials import Trials

from . import playback


class Tame(QObject):
    """{busy, said}; start(doc) searches, the edit is applied on the screen's thread (one undo step "Tame the peaks")."""
    changed = Signal()
    _done = Signal(object, str)

    def __init__(self, bridge, open_engine=playback.open_engine, parent=None):
        super().__init__(parent)
        self.bridge, self._open_engine = bridge, open_engine
        self.busy, self.said = False, ""
        self._done.connect(self._land)

    def start(self):
        doc = self.bridge.doc
        if self.busy or not doc.folder:
            return
        self.busy, self.said = True, "Finding the gentlest compressor that takes the peaks off…"
        self.bridge._set_status(self.said)
        self.changed.emit()
        data, folder = copy.deepcopy(doc.data), doc.folder
        threading.Thread(target=self._search, args=(data, folder), daemon=True).start()

    def _search(self, data, folder):
        try:
            self._done.emit(*search(data, folder, self._open_engine))
        except Exception as e:   # noqa: BLE001 - said in the sheet and the top bar, never a quiet nothing
            self._done.emit(None, f"Taming the peaks failed: {e}")

    def _land(self, ops, words):
        self.busy = False
        if ops:
            self.bridge._apply(ops, "Tame the peaks")
            words += " Ctrl+Z takes it back."
        self.said = words
        self.bridge._set_status(words)
        self.changed.emit()


def search(data: dict, folder, open_engine) -> tuple[list | None, str]:
    """(ops, words): the compressor that lands the song on its target within at most fit.LOT_DB of limiting (or the
    master's own Most limiting when that is lower), measured on the song as it is now; (None, why) when none does."""
    m = (data.get("master") or [{}])[0]
    goal, limit = m.get("loudness", -16), min(m.get("maxLimit", 2), fit.LOT_DB)
    m.update(maxLimit=limit, gentle=True)          # (a copy) measured at the limiting it should end with, not at what was pushed before
    renders = Path(folder) / "renders"
    renders.mkdir(parents=True, exist_ok=True)
    eng = open_engine()
    try:
        with tempfile.TemporaryDirectory(prefix="tame_", dir=renders) as tmp:
            view = SimpleNamespace(data=data, folder=folder)
            r = Trials(eng, Path(tmp)).one(compile_doc(view))
            short = goal - r["lufs"]
            if short < fit.SHORT_OK and fit.need_db(r) <= fit.LOT_DB:
                return None, f"Nothing to tame: the song reaches {goal:g} LUFS with {fit.need_db(r):.1f} dB of limiting."
            got = fit._tame(goal, limit, max(short, fit.SHORT_OK), r, data, eng, Path(tmp))
    finally:
        eng.close()
    if not got.get("ops"):
        return None, got.get("words", "No gentle compressor reaches the target here.")
    named = {t["id"]: t.get("name") or t["id"] for t in data.get("tracks", [])}
    names = " and ".join(named.get(w, w) for w in got["tracks"])
    return got["ops"], (f"Peaks tamed on {names}: a gentle compressor, the track kept where it sat. The master now needs "
                        f"{got['limit_db']:.1f} dB of limiting (was {fit.need_db(r):.1f}).")
