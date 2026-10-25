"""Play / stop and keeping the sound current: the document is re-rendered (debounced) after each change, the
newest render goes to the engine's live transport (live_transport.py: the first one opens it, stopped, so the first
play starts at once, unless the person chose Use speakers alone; later ones are loaded while it plays on), and the playhead follows the speaker's position the engine reports.

Nothing renders while a drag is open (`held`): a draw-click followed by a drag on its length, or the next drag
right after a release, never shares the machine with a render; the drag's change renders once, when it lands. The
engine itself runs below the screen's priority (playback.py), so a render that is running keeps the screen at 60 fps.

Play waits for a render that is on its way (never plays a stale one silently). A failed render is loud: `failed`
carries the error, the state line says so, and only then is the last good render played, saying that it is. When the
engine's player cannot open (no sound output) or dies, that is loud too and the playhead runs on a clock.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal

from rostrum_sound import settings

from .live_transport import LivePlay
from .playback import Renderer

DEBOUNCE_MS = 300


class Transport(QObject):
    playingChanged = Signal()
    renderChanged = Signal()
    stateChanged = Signal()
    moved = Signal(float)          # the playhead while playing (seconds)
    failed = Signal(str)
    said = Signal(str)             # a plain one-line notice for the status (not an error)

    def __init__(self, schedule_fn, length_fn, parent=None, held=lambda: False, pointing=lambda: False):
        super().__init__(parent)
        self._schedule, self._length, self._held, self._pointing = schedule_fn, length_fn, held, pointing
        self.last: dict = {}
        self.state, self.stale, self._want, self._at, self._render_failed = "Rendering…", True, False, 0.0, False
        self.loop: tuple[float, float] | None = None      # ⟳ Loop: (start, end) of the time range while on
        self.renderer = Renderer(self)
        self.renderer.rendered.connect(self._rendered)
        self.renderer.failed.connect(self._failed)
        self.player = LivePlay(self)
        self.player.problem.connect(self.failed)
        self.player.changed.connect(self._show_state)
        self.player.ended.connect(self._ended)
        self._tick = QTimer(self, interval=33, timeout=self._advance)
        self._debounce = QTimer(self, singleShot=True, interval=DEBOUNCE_MS, timeout=self.render)
        self._told = QTimer(self, singleShot=True, interval=50, timeout=self._tell)

    @property
    def playing(self) -> bool:
        return self.player.playing

    def busy(self) -> bool:
        """A render is waiting or running (screenshots wait for it)."""
        return self._debounce.isActive() or not self.renderer.idle() or self.stale

    def changed(self):
        """The document changed: render again shortly (edits in quick succession render once)."""
        self.stale = True
        self._debounce.start()

    def render(self):
        self.stale = True
        if self._held() or self._pointing():   # a drag is open (its release asks again), or the person is clicking:
            self._debounce.start()             # the render thread's work on the song shares the screen's time
            return
        self._set_state("Rendering…")
        try:
            self.renderer.request(self._schedule())
        except Exception as e:  # noqa: BLE001  e.g. a marker reference that no longer resolves
            self._failed(f"Error: render: {getattr(e, 'line', lambda: e)()}")

    def toggle(self, t: float):
        if self.player.playing or self._want:
            self._want = False
            self.player.stop()
            self._tick.stop()
            self.playingChanged.emit()
        elif self.busy():
            self._want, self._at = True, t    # starts when the render lands
        elif not self.last:
            self.failed.emit("Error: play: nothing to play, the render failed (the reason is above)")
        else:
            self._play(t)

    def seek(self, t: float):
        if self.player.playing:
            self.player.seek(t)

    def _play(self, t):
        if self.loop and not self.loop[0] <= t < self.loop[1]:
            t = self.loop[0]                    # looping: play starts inside the loop
        self.player.play(t)
        self._tick.start()
        self.playingChanged.emit()

    def _rendered(self, result):
        if result.get("restarted"):
            self.said.emit(result["restarted"])
        self.last, self.stale, self._render_failed = dict(result), False, False
        self.player.load(self.last["file"])
        if not self._want and not settings.load()["exclusive"]:
            self.player.warm()       # the first render opens the player, stopped: the first Play starts at once (it
                                     # waited ~0.5 s for the process); "Use speakers alone" keeps them free until Play
        self._tell()                 # what shows the render (loudness, meters, Problems): once the pointer is quiet
        if self._want:
            self._want = False
            self._play(self._at)

    def _tell(self):
        """The render's news, unless a drag is open or the person is pointing (5-30 ms the pointer must not wait
        for; a drag's drop renders again): then a moment later, asked again."""
        if self._held() or self._pointing():
            return self._told.start()
        self.renderChanged.emit()
        self._show_state()

    def _failed(self, line):
        self.stale, self._render_failed = False, True
        self.failed.emit(line)
        self._show_state()
        if self._want and self.last:
            self._want = False
            self._play(self._at)

    def _show_state(self):
        if self._render_failed:
            text = "Render failed" + (": playing the last good render" if self.last else "")
        elif not self.player.alive:
            text = "No sound output: the playhead runs on a clock (the reason is in the status line)"
        else:
            text = ""
        self._set_state(text)

    def end(self) -> float:
        """Where the song ends: the render's own length (the last sound, or the length that was set), the one source
        for "the end". The ruler's room to write in (the view) is a different thing and never stops playback."""
        return float(self.last["seconds"]) if self.last.get("seconds") else self._length()

    def _ended(self, t):
        self._tick.stop()
        self.moved.emit(min(t, self.end()))     # the player's end line says the newest loaded render's length (play.rs)
        self.playingChanged.emit()

    def _advance(self):
        t = self.player.position()
        if self.loop and self.player.playing and t >= self.loop[1]:   # ⟳ Loop: back to the range's start
            self.player.seek(self.loop[0])
            t = self.loop[0]
        if t >= self.end():                    # on the clock (no player), the song's end stops it
            self.toggle(t)
            t = self.end()
        self.moved.emit(t)

    def _set_state(self, text):
        if text != self.state:
            self.state = text
            self.stateChanged.emit()

    def close(self):
        self._tick.stop()
        self._debounce.stop()
        self._told.stop()
        self.player.close()
        self.renderer.close()
