"""Every press answers in the same frame, and a wait shows life (INTERACTION.md principles 1, 2 and 8): "paint, then run".

A person's click on a kit control or a key's shortcut that runs an action KNOWN TO BE LONG (it says `heavy`, or its last run
took 0.2 s or more) does not run inside that event; a quick one runs at once (its press look is on screen from the
mouse-down, with no fade, and a key's result lands in the key's own frame). `ACK.run`:
  1. marks the control that was clicked `working` (it keeps its pressed look: Button, IconButton …) and arms the top bar's
     working line, its note ("Group · 5 layers…") and its job chip (TopBar.qml / WorkingLine.qml read `ack`);
  2. waits for that frame to be on screen (after_frame.AfterFrame: its frameSwapped);
  3. runs the action; then puts everything back and runs the next press that came meanwhile (queued, never dropped).

Why the line is armed BEFORE the run, not started 0.2 s into it: Python runs on the GUI thread, and while an action runs
nothing on that thread can change the screen. So the line, the note and the chip are put on screen in step 1 already, at
zero opacity, with render-thread animators (OpacityAnimator, XAnimator) that keep running while the GUI thread is busy:
the line and the note appear 0.2 s in (`lineAfter`), the chip 1 s in, the line moves the whole time; an action that is
done sooner takes them away before anyone saw them. Where Qt draws on the GUI thread (a software window) the animators
stop with it, so an action known to be long shows them at once instead: one that says so (`heavy`), or one whose last
run took 0.2 s or more (measured here, per action id). The chip of a plain action says it can't be stopped part-way
(its Cancel would be a fake button: nothing can run while it does).

A job that should be stoppable runs in turns: anything given to `run` returns a generator, or an action hands its long
part over with `ACK.in_turns(generator)` (it keeps the run's place in the line); ack drives it
a few ms per turn between frames (the window paints, clicks are heard, `yield 0.4` sets the chip's progress) and the
chip's Cancel closes it (GeneratorExit inside it: its `finally` puts things back) and calls `cancel`, when given.

Only a person's input is deferred: a click (the kit control calls `ack.by(control)` just before its clicked()) or a
key (KeyShortcut reports it to typed_word, which tells `key()`), plus anything that comes while a run is queued or going
(it keeps its place in the line). A script or an agent calling the same hub door runs at once, as before, and reads its
result straight after. `ActionHub._go` asks `defer` first (one line), so every action of every app gets this.

Also here (K7): `PopupPresses`, a press inside an open kit popup belongs to the area that opened it (SmallPopup keeps
`openerArea`), so Ctrl+A and Delete act where the person was; and `system_reduce_motion()`, Windows' own "Show
animations in Windows" setting, which Theme.reduceMotion starts from (K10).
"""
from __future__ import annotations

import inspect
import sys
import time

from PySide6.QtCore import Property, QEvent, QObject, QPointF, QRectF, QTimer, Signal, Slot

from . import qt_faults
from .after_frame import AfterFrame
from .gui_filter import GuiFilter

LINE_MS = 200       # the working line and note show this long into a run
CHIP_MS = 1000      # the job chip (with Cancel, or "can't be stopped part-way") this long in
HEAVY_S = 0.2       # an action that took this long last time shows its line at once
TURN_MS = 12        # a job in turns works this long, then the window paints and hears clicks


class AckJob(QObject):
    """The running job as JobChip reads it: state ("running" or ""), note, progress (0..1, -1 unknown), cancellable,
    cancel(), dismiss(). It has no sheet to open (JobChip shows "Open …" only for a job with setOpen)."""
    changed = Signal()

    def __init__(self, ack):
        super().__init__(ack)
        self._ack, self._state, self._note, self._progress, self._cancellable = ack, "", "", -1.0, False

    def set(self, **kw):
        for k, v in kw.items():
            setattr(self, "_" + k, v)
        self.changed.emit()

    state = Property(str, lambda s: s._state, notify=changed)
    note = Property(str, lambda s: s._note, notify=changed)
    progress = Property(float, lambda s: s._progress, notify=changed)
    cancellable = Property(bool, lambda s: s._cancellable, notify=changed)

    @Slot()
    def cancel(self):
        self._ack.cancel()

    @Slot()
    def dismiss(self):
        pass                    # a run that raised is reported by qt_faults, never left as a failed chip


class _Run:
    __slots__ = ("fn", "note", "key", "heavy", "item", "cancel", "gen", "t0")

    def __init__(self, fn, note, key, heavy, item, cancel):
        self.fn, self.note, self.key, self.heavy, self.item, self.cancel = fn, note, key, heavy, item, cancel
        self.gen, self.t0 = None, 0.0


def _mark(item, on: bool):
    """The control's working look (a kit control with a `working` property); a freed one is left alone."""
    try:
        if item is not None and item.metaObject().indexOfProperty("working") >= 0:
            item.setProperty("working", on)
    except RuntimeError:        # its QML item went away meanwhile (a row rebuilt by the action)
        pass


class Ack(QObject):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self._queue: list[_Run] = []
        self._cur: _Run | None = None
        self._person, self._by, self._inside = False, None, False
        self._took: dict[str, float] = {}           # action id -> its last run's seconds
        self._working, self._note, self._line_after = False, "", LINE_MS
        self._job = AckJob(self)
        self._start = AfterFrame(self._begin, self)

    # ---- what QML reads -------------------------------------------------------------------------------------------
    working = Property(bool, lambda s: s._working, notify=changed)        # a run is armed or going: the line is armed
    note = Property(str, lambda s: s._note, notify=changed)               # its words, "Group · 5 layers…"
    lineAfter = Property(int, lambda s: s._line_after, notify=changed)    # ms before the line and note show (0: at once)
    chipAfter = Property(int, lambda s: 0 if s._line_after == 0 and s._cur and s._took.get(s._cur.key, 0) >= CHIP_MS / 1000
                         else CHIP_MS, notify=changed)
    job = Property(QObject, lambda s: s._job, constant=True)              # JobChip's job

    # ---- who pressed ----------------------------------------------------------------------------------------------
    @Slot(QObject)
    def by(self, control):
        """A kit control was clicked (called just before its clicked()): what runs from this event is a person's, and
        `control` keeps its pressed look until it is done."""
        self._person, self._by = True, control
        QTimer.singleShot(0, self._forget)          # only this event's runs

    @Slot()
    def key(self):
        """A shortcut fired (typed_word.ran, from KeyShortcut): the run it starts is a person's."""
        self.by(None)

    def _forget(self):
        self._person, self._by = False, None

    def long(self, key: str = "", heavy: bool = False) -> bool:
        """An action known to take a while: it says so (`heavy`), or its last run took 0.2 s or more."""
        return heavy or (bool(key) and self._took.get(key, 0.0) >= HEAVY_S)

    def wanted(self, key: str = "", heavy: bool = False) -> bool:
        """A run asked now should wait its turn: a person's press of an action known to be long (its press and its
        "Grouping 200 layers…" line reach the screen first), or one that comes while others wait (order is kept).
        A quick action runs at once, inside its event: the pressed look is already on screen from the mouse-down (no
        fade), and a key's result shows in the key's own frame; deferring every press made every scripted key land a
        frame late (seven 2D screen checks read the result right after the key)."""
        return not self._inside and ((self._person and self.long(key, heavy)) or self._cur is not None
                                     or bool(self._queue))

    def took(self, key: str, seconds: float):
        """A person's action ran at once and took `seconds` (the hub times it): its next press is known long or not."""
        if self._person and key:
            self._took[key] = seconds

    def forget_times(self):
        """A new window: no action is known long yet (what one test or session measured never defers another's)."""
        self._took.clear()

    def defer(self, fn, *args, note: str = "", key: str = "", heavy: bool = False) -> bool:
        """`fn(*args)` goes through `run` when `wanted()` (True: it will run later); False: the caller runs it now."""
        if not self.wanted(key, heavy):
            return False
        self.run(lambda: fn(*args), note=note, key=key, heavy=heavy)
        return True

    # ---- the line of runs -----------------------------------------------------------------------------------------
    def run(self, fn, note: str = "", key: str = "", heavy: bool = False, cancel=None):
        """Run `fn()` once its press is on screen, after any run before it. `fn` may return a generator: it then runs in
        turns (see the module's words) and may be cancelled. `cancel()`: also called when the person cancels."""
        self._queue.append(_Run(fn, note, key or note, heavy, self._by, cancel))
        if self._cur is None:
            self._next()

    def in_turns(self, gen, cancel=None):
        """The rest of the run going now goes on in turns (an app's action hands its long part over: the hub's door
        returns nothing, so the action says it here): `gen` yields between steps (a number = its progress 0..1), the
        window paints and hears clicks between turns, and the chip's Cancel stops it. Outside a run: a run of its own."""
        r = self._cur
        if r is None or not self._inside or r.gen is not None:
            return self.run(lambda: gen, cancel=cancel)
        r.gen, r.cancel = gen, cancel or r.cancel

    def _next(self):
        if not self._queue:
            self._cur = None
            if self._working:
                self._working, self._note = False, ""
                self._job.set(state="", note="", progress=-1.0, cancellable=False)
                self.changed.emit()
            return
        r = self._cur = self._queue.pop(0)
        _mark(r.item, True)
        long_before = r.heavy or self._took.get(r.key, 0.0) >= HEAVY_S
        self._working, self._note, self._line_after = True, (r.note + "…") if r.note else "Working…", 0 if long_before else LINE_MS
        self._job.set(state="running", note=self._note.rstrip("…"), progress=-1.0, cancellable=r.cancel is not None)
        self.changed.emit()
        self._start.ask()               # step 2: the press, the note and the armed line reach the screen first

    def _begin(self):
        r = self._cur
        if r is None:
            return
        r.t0 = time.monotonic()
        self._inside = True
        try:
            out = r.fn()
        except Exception:               # noqa: BLE001  said by name, and the next press still runs
            out = None
            qt_faults.python_error(f'"{r.note or r.key}"', r.note)
        finally:
            self._inside = False
        if inspect.isgenerator(out) and r.gen is None:
            r.gen = out
        if r.gen is not None:
            self._job.set(cancellable=True)
            QTimer.singleShot(0, self, self._turn)
            return
        self._end(r)

    def _turn(self):
        r = self._cur
        if r is None or r.gen is None:
            return
        stop = time.monotonic() + TURN_MS / 1000
        self._inside = True
        try:
            while time.monotonic() < stop:
                p = next(r.gen)
                if isinstance(p, (int, float)) and not isinstance(p, bool):
                    self._job.set(progress=max(0.0, min(1.0, float(p))))
        except StopIteration:
            self._inside = False
            return self._end(r)
        except Exception:               # noqa: BLE001
            self._inside = False
            qt_faults.python_error(f'"{r.note or r.key}"', r.note)
            return self._end(r)
        finally:
            self._inside = False
        QTimer.singleShot(0, self, self._turn)      # the window paints and hears clicks between turns

    def _end(self, r: _Run):
        if r is not self._cur:
            return
        self._took[r.key] = time.monotonic() - r.t0
        _mark(r.item, False)
        self._next()

    @Slot()
    def cancel(self):
        """The chip's Cancel: a job in turns stops at its next turn (GeneratorExit inside it) and its `cancel` runs."""
        r = self._cur
        if r is None or (r.gen is None and r.cancel is None):
            return
        try:
            if r.gen is not None:
                r.gen.close()
            if r.cancel is not None:
                r.cancel()
        except Exception:               # noqa: BLE001
            qt_faults.python_error(f'cancelling "{r.note or r.key}"', r.note)
        r.gen = None
        self._end(r)

    def busy(self) -> bool:
        """A run is waiting or going (a script waits for it like for after_frame's work)."""
        return self._cur is not None or bool(self._queue)

    def flush(self, limit: float = 10.0):
        """Run everything waiting now (a script or a test that must read the result)."""
        from PySide6.QtCore import QCoreApplication
        end = time.monotonic() + limit
        while self.busy() and time.monotonic() < end:
            if self._cur is not None and self._start.due:
                self._start.flush()
            QCoreApplication.processEvents()


ACK = Ack()          # one per process, like after_frame's turns: QML reads it as `ack` (app.start sets it)


# ---- K7: a press inside a popup belongs to its opener ---------------------------------------------------------------
class PopupPresses(GuiFilter):
    """A press inside an open kit popup gives the keys' area back to the area that opened it (SmallPopup.openerArea):
    the popup lies over some other area (Repeat's list over the arrangement), and the window's area watcher
    (focus_areas.py) went by the point alone, so Ctrl+A after a pick in the list took every track. Installed BEFORE the
    area watcher (Qt asks the filter installed last first), so this one runs after it has set the area."""

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.watch(win)
        ACK.forget_times()              # a new window (app.start): nothing measured before defers its presses

    def on_event(self, obj, event):
        if obj is not self.win or event.type() != QEvent.Type.MouseButtonPress:
            return False
        area = opener_area(self.win, event.position())
        if area and self.win.metaObject().indexOfProperty("focusArea") >= 0 and self.win.property("focusArea") != area:
            self.win.setProperty("focusArea", area)
        return False


def opener_area(win, at) -> str:
    """The area that opened the newest open kit popup under the window point `at` ("" when none is there)."""
    ov = next((c for c in win.contentItem().childItems() if c.metaObject().className() == "QQuickOverlay"), None)
    if ov is None:
        return ""
    p = QPointF(at.x(), at.y())
    for c in reversed(ov.childItems()):             # the newest popup is drawn last
        if c.isVisible() and c.mapRectToScene(QRectF(0, 0, c.width(), c.height())).contains(p):
            pop = c.parent()                       # a popup's item belongs to its Popup
            area = pop.property("openerArea") if pop is not None else None
            return area if isinstance(area, str) else ""
    return ""


# ---- K10: Windows' own "show animations" ------------------------------------------------------------------------------
def system_reduce_motion() -> bool:
    """Windows' "Animation effects" switch is off (SystemParametersInfo SPI_GETCLIENTAREAANIMATION): the kit moves
    nothing (Theme.reduceMotion starts from this). False elsewhere, or when it can't be read."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        on = ctypes.c_int(1)
        if not ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(on), 0):   # SPI_GETCLIENTAREAANIMATION
            return False
        return not on.value
    except Exception:       # noqa: BLE001  no setting read: motion stays on
        return False
