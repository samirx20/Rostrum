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
        self._landing = False
        bridge.docChanged.connect(self._stale)

    def _stale(self):
        """Any other change to the song makes the last answer old news (the edit this applied does not)."""
        if not self._landing and self.said and not self.busy:
            self.said = ""
            self.changed.emit()

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
            self._landing = True
            try:
                self.bridge._apply(ops, "Tame the peaks")
            finally:
                self._landing = False
            words += " Ctrl+Z takes it back."
        self.said = words
        self.bridge._set_status(words)
        self.changed.emit()


WORTH_DB = 1.0          # taming that takes less limiting off than this is not offered as done


def _and(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1] if names else ""


def search(data: dict, folder, open_engine) -> tuple[list | None, str]:
    """(ops, words): the gentlest compressor that lands the song on its target with the least limiting it can: first
    within fit.LOT_DB (or the master's own Most limiting when that is lower), else one step up, half way to what the
    target needs untamed (still less squashing than the push alone); measured on the song as it is now. (None, why)
    when none takes enough off to be worth it."""
    m = (data.get("master") or [{}])[0]
    goal, own = m.get("loudness", -16), m.get("maxLimit", 2)
    named = {t["id"]: t.get("name") or t["id"] for t in data.get("tracks", [])}
    renders = Path(folder) / "renders"
    renders.mkdir(parents=True, exist_ok=True)
    eng = open_engine()
    try:
        with tempfile.TemporaryDirectory(prefix="tame_", dir=renders) as tmp:
            view = SimpleNamespace(data=data, folder=folder)
            limits, need, got, tried = [min(own, fit.LOT_DB)], None, {}, []
            while limits:
                limit = limits.pop(0)
                m.update(maxLimit=limit, gentle=True)     # (a copy) measured at the limiting it should end with
                r = Trials(eng, Path(tmp)).one(compile_doc(view))
                need = fit.need_db(r) if need is None else need
                short = goal - r["lufs"]
                if short < fit.SHORT_OK:
                    if not tried:
                        return None, f"Nothing to tame: the song reaches {goal:g} LUFS with {need:.1f} dB of limiting."
                    break
                tried.append(limit)
                got = fit._tame(goal, limit, short, r, data, eng, Path(tmp))
                if got.get("ops"):
                    break
                if len(tried) == 1 and need - limit > 1.5:     # one step up: still well under what the push alone needs
                    limits.append(round((limit + need) / 2, 1))
    finally:
        eng.close()
    if not got.get("ops"):
        who = _and([named.get(w, w) for w in got.get("tracks") or []]) or "several tracks"
        return None, (f"No gentle compressor takes enough off here: the peaks come from {who} together. "
                      f"Push to the target ({need:.1f} dB of limiting) or keep it dynamic.")
    names = _and([named.get(w, w) for w in got["tracks"]])
    if need - got["limit_db"] < WORTH_DB:
        return None, (f"Taming the peaks on {names} would take only {need - got['limit_db']:.1f} dB of limiting off "
                      f"({need:.1f} → {got['limit_db']:.1f}): not worth a compressor on each. Nothing was changed.")
    return got["ops"], (f"Peaks tamed on {names}: a gentle compressor, the track kept where it sat. The master now needs "
                        f"{got['limit_db']:.1f} dB of limiting (was {need:.1f}).")
