"""The render sheet's time estimate (SPEC §11.2): "Measuring…", then "About 6 min · 120 frames · 3 s a frame", the probe's
picture, a note when another render is using the graphics card, and the budget with the one-setting changes that fit.

It never guesses: the number comes from rostrum3d.estimate_job (a probe through the same engine path as the real render,
kept by scene) scaled by rostrum3d.mcp.estimate.scale, exactly as the render_estimate tool does. A change that only
alters samples, size or frames re-scales the kept measurement at once; a change to the scene (or opening the sheet with
nothing kept) measures again 0.4 s later, in the background on its own engine, never while one of our renders runs.

It never says "Measuring…" for ever: from the moment it says it, a deadline (the probe's budget plus the wait for the
card) runs on the window's clock; when it passes, the probe's engine is ended by its PID and the row says "Couldn't
measure: <why>". An answer from a probe given up on is dropped. `use_recorded(m)` answers from a fixed measurement and
never probes (the layout check: fast and certain; the real probe is proved by tools/estimate_check.py).
"""
from __future__ import annotations

import re
import threading

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from rostrum3d import estimate_job, gpu_busy
from rostrum3d.engine import Engine, own_pids
from rostrum3d.mcp.estimate import human, scale
from rostrum3d.runtime import find_exe

DELAY_MS = 400
DEADLINE_S = estimate_job.BUDGET_S + 30   # the probe's own budget, plus waiting for the card and the engine's start
UNITS = {"s": 1, "sec": 1, "m": 60, "min": 60, "h": 3600, "hour": 3600}


def parse_budget(text: str) -> float | None:
    """"10 min", "90 s", "1.5 h", "10" (minutes) -> seconds; "" -> None (no budget). Anything else raises ValueError."""
    t = text.strip().lower()
    if not t:
        return None
    m = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*([a-z]*)", t)
    unit = m and next((v for k, v in UNITS.items() if m.group(2) in (k, k + "s", "")), None) if m else None
    if not m or unit is None:
        raise ValueError(f'"{text}" is not a time: type it like 10 min, 90 s or 1 h')
    return float(m.group(1).replace(",", ".")) * (60 if not m.group(2) else unit)


class Estimate(QObject):
    changed = Signal()
    _landed = Signal(object, str, str, int)       # (measurement, its key, error line, probe number): from the worker thread
    _card = Signal(str)                           # the card's state now, in words ("" = free): from a short check

    def __init__(self, sheet, make_engine=Engine, parent=None):
        super().__init__(parent or sheet)
        self._sheet, self._make_engine, self._engine = sheet, make_engine, None
        self._state, self._text, self._error, self._m, self._key, self._e = "", "", "", None, "", {}
        self._thread, self._budget, self._wanted = None, None, ""
        self._exe = getattr(make_engine, "exe", None) or find_exe()     # the engine build is part of the probe's key
        self._timer = QTimer(self, singleShot=True, interval=DELAY_MS)
        self._timer.timeout.connect(self._probe)
        self._landed.connect(self._on_landed)
        self._card_now = ""
        self._card.connect(self._on_card)
        self._deadline = QTimer(self, singleShot=True, interval=int(DEADLINE_S * 1000))
        self._deadline.timeout.connect(self._give_up)
        self._run, self._recorded = 0, None      # the probe now wanted (older answers are dropped); a fixed measurement

    # ---- what QML shows ---------------------------------------------------------------------------------------
    @Property(str, notify=changed)
    def state(self):
        """"" | "measuring" | "ready" | "failed"."""
        return self._state

    @Property(str, notify=changed)
    def text(self):
        return "Measuring…" if self._state == "measuring" else self._error if self._state == "failed" else self._e.get("text", "")

    @Property(str, notify=changed)
    def how(self):
        if self._state != "ready" or not self._m:
            return ""
        return ("from a test frame of this scene, kept" if self._m.get("cached") else "from a test frame just rendered") + " on this computer"

    @Property(str, notify=changed)
    def card(self):
        """Another render was using the graphics card while it was measured (so the number runs high), in words."""
        return ((self._m or {}).get("gpu_busy", "") or self._card_now) if self._state == "ready" else ""

    @Property(str, notify=changed)
    def picture(self):
        p = (self._m or {}).get("picture", "")
        return QUrl.fromLocalFile(p).toString() if p and self._state == "ready" else ""

    @Property(float, notify=changed)
    def seconds(self):
        return float(self._e.get("seconds", 0.0)) if self._state == "ready" else 0.0

    @Property(str, notify=changed)
    def budget(self):
        return human(self._budget) if self._budget else ""

    @Property(bool, notify=changed)
    def over(self):
        return bool(self._budget) and self._state == "ready" and self._e.get("seconds", 0) > self._budget

    @Property("QVariantList", notify=changed)
    def fits(self):
        """Over the budget: the one-setting changes that fit, each {field, value, text} for a click."""
        return self._sheet.fitting(self._m, self._budget) if self.over else []

    # ---- what changes it --------------------------------------------------------------------------------------
    @Slot(str, result=str)
    def setBudget(self, text):
        """"10 min" (or "" for none); returns "" or the sentence saying why it is not a time."""
        try:
            self._budget = parse_budget(text)
        except ValueError as e:
            return str(e)
        self.changed.emit()
        return ""

    def refresh(self):
        """Something in the sheet or the scene changed: re-scale the kept measurement at once if it still applies,
        else say "Measuring…" and measure shortly (a run of quick changes measures once)."""
        if not self._sheet.open and self._state == "measuring":
            self._abandon()                               # closed while measuring: the probe ends; reopening measures again
            self._state = ""
        if not self._sheet.open or self._sheet.running():    # while it renders, the row keeps what it said
            return self._timer.stop()
        try:
            scene, info, s, frames = self._sheet.plan_now()
            key = estimate_job.probe_key(scene, s, self._exe)
        except Exception as e:  # noqa: BLE001  the shot can't be rendered as it is: say why, never a number
            return self._set("failed", None, "", f"Couldn't measure: {e}")
        if self._recorded is not None:
            return self._set("ready", self._recorded, "recorded")
        if key == self._key and self._m is not None:
            return self._set("ready", self._m, key)
        if (m := estimate_job.cached(scene, s, self._exe)) is not None and not m.get("gpu_busy"):
            return self._set("ready", m, key)
        if self._state == "measuring" and key == self._wanted:
            return                                        # the same picture is already waiting or being measured
        self._wanted = key
        self._set("measuring", None, "")
        self._deadline.start()                            # restarted: a new picture to measure gets the whole time
        self._timer.start()

    def use_recorded(self, m: dict):
        """Answer from this measurement (estimate_job's shape) and never probe: the layout check's fixed estimate."""
        self._recorded = m
        self.refresh()

    def check_card(self):
        """The sheet opened: is another job on the graphics card now (a kept measurement was made on a free one)?"""
        mine = own_pids()
        threading.Thread(target=lambda: self._card.emit(gpu_busy.busy(own_pids=mine)), name="card-check", daemon=True).start()

    def _on_card(self, text):
        self._card_now = text
        self.changed.emit()

    def _probe(self):
        if self._thread is not None and self._thread.is_alive() or self._sheet.gpu_ours():
            return self._timer.start()                    # one of ours is on the card: measure once it is free
        try:
            scene, info, s, _ = self._sheet.plan_now()
        except Exception as e:  # noqa: BLE001
            return self._set("failed", None, "", f"Couldn't measure: {e}")

        mine, run = own_pids(), self._run                                 # this window's engines (the viewport's) are not "another job"

        def made():
            self._engine = self._make_engine()
            return self._engine

        def work():
            try:
                m = estimate_job.measure(scene, info, s, "render sheet", make_engine=made, own_pids=mine)
                self._landed.emit(m, estimate_job.probe_key(scene, s, self._exe), "", run)
            except Exception as e:  # noqa: BLE001  fail loudly: the row says what failed, never a number
                self._landed.emit(None, "", f"{e.subject} {e.problem}" if hasattr(e, "problem") else str(e), run)
            finally:
                self._engine = None
        self._thread = threading.Thread(target=work, name="render-estimate", daemon=True)
        self._thread.start()

    def _on_landed(self, m, key, error, run):
        if run != self._run:
            return                                        # a probe given up on (deadline, closed): its answer is stale
        self._deadline.stop()
        self._thread, self._wanted = None, ""
        if error:
            return self._set("failed", None, "", f"Couldn't measure: {error}")
        self._m, self._key = m, key
        self.refresh()                                    # the sheet may have changed while it measured

    def _give_up(self):
        """The deadline passed while it still said "Measuring…": end the probe and say so."""
        if self._state != "measuring":
            return
        waited = "the graphics card stayed busy with our own render" if self._thread is None else             f"the test frames gave no answer in {DEADLINE_S:.0f} s; the probe's engine was ended"
        self._abandon()
        self._set("failed", None, "", f"Couldn't measure: {waited}. Change a setting or reopen the sheet to try again.")

    def _abandon(self):
        """Drop the probe under way: its engine ended by its PID, its answer ignored, the next one starts afresh."""
        self._run += 1
        self._timer.stop()
        self._deadline.stop()
        e, self._engine, self._thread, self._wanted = self._engine, None, None, ""
        if e is not None:
            e.kill()

    def _set(self, state, m, key, error=""):
        self._state, self._error = state, error
        if m is not None:
            self._m, self._key = m, key
            _, _, s, frames = self._sheet.plan_now()
            self._e = scale(m, s, frames, mp4=False)
        self.changed.emit()

    def close(self):
        """The sheet or the window closes: no probe or engine of ours goes on."""
        self._abandon()
