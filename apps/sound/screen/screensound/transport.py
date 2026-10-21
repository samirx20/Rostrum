"""Play / stop and keeping the sound current: the document is re-rendered (debounced) after each change, the
newest render plays, and the playhead follows the player.

Play waits for a render that is on its way (never plays a stale one silently). A failed render is loud: `failed`
carries the error, the state line says so, and only then is the last good render played, saying that it is.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal

from .playback import Player, Renderer

DEBOUNCE_MS = 300


class Transport(QObject):
    playingChanged = Signal()
    renderChanged = Signal()
    stateChanged = Signal()
    moved = Signal(float)          # the playhead while playing (seconds)
    failed = Signal(str)

    def __init__(self, schedule_fn, length_fn, parent=None):
        super().__init__(parent)
        self._schedule, self._length = schedule_fn, length_fn
        self.last: dict = {}
        self.state, self.stale, self._want, self._at = "Rendering…", True, False, 0.0
        self.renderer = Renderer(self)
        self.renderer.rendered.connect(self._rendered)
        self.renderer.failed.connect(self._failed)
        self.player = Player(self)
        self.player.problem.connect(self.failed)
        self._tick = QTimer(self, interval=33, timeout=self._advance)
        self._debounce = QTimer(self, singleShot=True, interval=DEBOUNCE_MS, timeout=self.render)

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
            self._play(t)

    def _play(self, t):
        self.player.play(self.last["file"], t)
        self._tick.start()
        self.playingChanged.emit()

    def _rendered(self, result):
        self.last, self.stale = dict(result), False
        self.renderChanged.emit()
        self._set_state("" if self.player.has_output else "No sound output on this machine: rendered, not heard")
        if self.player.playing or self._want:
            self._want = False
            self._play(self.player.position() if self.player.playing else self._at)

    def _failed(self, line):
        self.stale = False
        self.failed.emit(line)
        self._set_state("Render failed" + (": playing the last good render" if self.last else ""))
        if self._want and self.last:
            self._want = False
            self._play(self._at)

    def _advance(self):
        t = self.player.position()
        if t >= self._length():
            self.toggle(t)
            t = self._length()
        self.moved.emit(t)

    def _set_state(self, text):
        self.state = text
        self.stateChanged.emit()

    def close(self):
        self._tick.stop()
        self._debounce.stop()
        self.player.close()
        self.renderer.close()
