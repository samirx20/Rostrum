"""The screen's player: one long-lived `rostrum-sound play` process (the engine's live transport, ENGINE_CONTRACT.md
§ play), so what plays is the engine's own render file (preview ≡ export) and a take is placed by the engine's clock
against what was heard, to the sample.

    p = LivePlay(); p.load(render_wav)       # the first play / arm starts the process; later renders send {"load"}
    p.play(t); p.stop(); p.seek(t); p.position()
    p.configure(mic=dir, midi=n, instrument=file, bpm=b, beats=n)   # a different set-up reopens it (position kept)
    p.set_state(countIn=1, record={"punch": [a, b]}, hear=True)      # remembered and sent again after a reopen

Out: `rolling`, `ended`, `take`, `note`, `level` (input peak dB), `problem` (loud lines), `changed` (opened / gone).
The process runs on the shared output (`--shared`: the device stays usable by other apps) unless the person chose
"Take over the speakers" in settings; the chosen speakers, microphone and buffer reach it as the engine's
environment (settings.engine_env). It is started only when it is first needed. When it cannot open or dies (no output device, no microphone) it says why, loudly, and the
playhead runs on a clock (`alive` False, `reason`). It is ended by its own handle, never by name. `program` is the
test seam: what replaces `[engine, "play"]` (fake_play.py speaks the same lines).
"""
from __future__ import annotations

import json
import subprocess
import threading
import time

from PySide6.QtCore import QObject, Signal
from rostrum_sound import settings

QUIT_S = 3


class LivePlay(QObject):
    rolling = Signal(float)
    ended = Signal(float)
    take = Signal("QVariantMap")
    note = Signal("QVariantMap")
    level = Signal(float)
    problem = Signal(str)
    changed = Signal()
    _line = Signal(int, "QVariantMap")         # from the reader thread, delivered on the screen's thread
    _gone = Signal(int, int, str)

    program: list[str] | None = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self._line.connect(self._on_line)
        self._gone.connect(self._on_gone)
        self._proc, self._gen, self.file, self.opts = None, 0, "", {}
        self.state: dict = {}
        self.ready: dict = {}
        self.alive, self.reason = True, ""
        self.playing, self.rolled, self._t, self._at = False, False, 0.0, time.monotonic()

    # ---- what the screen calls --------------------------------------------------------------------------------
    @property
    def mic(self) -> dict | None:
        """The open microphone (`rate`, `device`, `inputOffsetMs`), or None."""
        return self.ready.get("mic") if self._proc else None

    def load(self, file: str):
        """The newest render: sent to a running process (playback carries on), else kept for the first start."""
        self.file = file
        if self._proc:
            self.send({"load": file})
        elif self.alive and self._needs_open():
            self._open()                             # armed before the first render: the microphone opens now

    def configure(self, **opts):
        """mic (takes folder), midi (device), instrument (live.json), bpm, beats, beat_times (a JSON file of the
        beats in seconds, when the tempo changes): reopen when they changed. Other keys only mark a change."""
        opts = {k: v for k, v in opts.items() if v is not None}
        if opts != self.opts:
            self.opts = opts
            if self._proc or self._needs_open():
                self._open()
            else:
                self.alive, self.reason = True, ""    # the next play tries again
                self.changed.emit()

    def _needs_open(self) -> bool:
        return bool(self.opts.get("mic")) or self.opts.get("midi") is not None

    def set_state(self, **state):
        self.state.update(state)
        for k, v in state.items():
            if self._proc:
                self.send({k: v})

    def play(self, t: float):
        self._ensure()
        self.playing, self.rolled, self._t, self._at = True, False, t, time.monotonic()
        self.send({"play": {"from": t}})

    def stop(self):
        self._t, self.playing, self.rolled = self.position(), False, False
        self.send({"stop": True})

    def seek(self, t: float):
        self._t, self._at = t, time.monotonic()
        self.send({"seek": t})

    def position(self) -> float:
        """Where the speaker is (mix seconds): the engine's last `pos` plus the time since; on a clock without it."""
        if self.playing and (self.rolled or not self.alive):
            return self._t + time.monotonic() - self._at
        return self._t

    def close(self):
        self._end()

    # ---- the process ------------------------------------------------------------------------------------------
    def _ensure(self):
        if self._proc is None and self.alive and self.file:
            self._open()

    def _args(self) -> list[str]:
        if self.program is None:
            from rostrum_sound.engine import find_engine
            head = [str(find_engine()), "play"]
        else:
            head = list(self.program)
        o, args = self.opts, [self.file, "--from", str(round(self._t, 4))]
        if not settings.load()["exclusive"]:
            args.append("--shared")
        for key, flag in (("mic", "--mic"), ("midi", "--midi"), ("instrument", "--instrument"), ("bpm", "--bpm"),
                          ("beats", "--beats"), ("beat_times", "--beat-times")):
            if key in o:
                args += [flag, str(o[key])]
        return head + args

    def _open(self):
        if not self.file:
            return                                   # opened on the first play, once there is a render
        was, t = self.playing, self.position()
        self._end()
        self._t, self.alive, self.reason, self.ready = t, True, "", {}
        self._gen += 1
        try:
            self._proc = subprocess.Popen(self._args(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE, text=True, encoding="utf-8",
                                          env=settings.engine_env())
        except OSError as e:
            self._dead(f"the engine's player could not start: {e}")
            return
        gen, proc, err = self._gen, self._proc, []
        threading.Thread(target=lambda: err.extend(proc.stderr), daemon=True).start()
        threading.Thread(target=self._read, args=(gen, proc, err), daemon=True).start()
        for k, v in self.state.items():
            self.send({k: v})
        if was:
            self.play(t)
        self.changed.emit()

    def _read(self, gen, proc, err):
        for line in proc.stdout:
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(msg, dict):
                self._line.emit(gen, msg)
        code = proc.wait()
        time.sleep(0.05)                             # the last of stderr
        try:
            self._gone.emit(gen, code, "".join(err).strip())
        except RuntimeError:                         # the screen closed first: nobody is left to tell
            pass

    def send(self, msg: dict):
        if self._proc is None:
            return
        try:
            self._proc.stdin.write(json.dumps(msg) + "\n")
            self._proc.stdin.flush()
        except OSError:
            pass                                     # it is ending; _on_gone says why

    def _on_line(self, gen, m):
        if gen != self._gen:
            return
        if "ready" in m:
            self.ready = m["ready"]
            self.changed.emit()
        elif "pos" in m:
            t = m["pos"].get("t")
            if t is not None and self.playing:
                self._t, self._at, self.rolled = float(t), time.monotonic(), True
        elif "rolling" in m:
            self._t, self._at, self.rolled = float(m["rolling"]), time.monotonic(), True
            self.rolling.emit(self._t)
        elif "end" in m:
            self._t, self.playing, self.rolled = float(m["end"]), False, False
            self.ended.emit(self._t)
        elif "take" in m:
            self.take.emit(m["take"])
        elif "note" in m:
            self.note.emit(m["note"])
        elif "input" in m:
            self.level.emit(float(m["input"].get("peakDb", -100.0)))
        elif "error" in m:
            self.problem.emit(f"Error: playback: {m['error']}")

    def _on_gone(self, gen, code, err):
        if gen != self._gen or self._proc is None:
            return
        self._t, self._at = self.position(), time.monotonic()
        self._proc = None
        what = "could not open" if not self.ready else "stopped"
        self._dead(f"the engine's player {what} (exit code {code}): {err or '(nothing on stderr)'}")

    def _dead(self, reason):
        self._proc, self.alive, self.reason = None, False, reason
        self.problem.emit(f"Error: playback: {reason}")
        self.changed.emit()

    def _end(self):
        """Quit the running process (its own handle): ask, then end it if it does not go."""
        proc, self._proc = self._proc, None
        self._gen += 1
        if proc is None:
            return
        try:
            proc.stdin.write('{"quit": true}\n')
            proc.stdin.close()
        except OSError:
            pass
        try:
            proc.wait(QUIT_S)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
