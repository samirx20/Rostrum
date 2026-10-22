"""Slots and handlers for a bridge that live outside the bridge class (no Qt object of their own).

Two ways; each leaves the existing bridges as they are:
- A slot mix-in: a plain class (no base) whose methods carry `@Slot`. List it before DocBridge in the bridge's
  bases and QML sees its slots as the bridge's own: `class Bridge2D(ZoomSlots, DocBridge)`. The mix-in reaches the
  bridge through `self` (`self.doc`, `self.who`, `self._apply`, `self._guard`). `SlotMixin` below only names the idea.
- (S36: `bridge.attach(name, obj)` is gone: a dynamic property on the bridge reads as null from QML. A part that is a
  QObject of its own is offered with `@Property(QObject, constant=True)` on the app's bridge, or through `invoke`.)
- `bridge.handle("zoomTo", fn)`: a Python function registered by name from any module; QML calls
  `bridge.invoke("zoomTo", [args])`. A handler that raises RostrumError is reported, never swallowed (like an edit).
"""
from __future__ import annotations

from rostrum_core import RostrumError, codes


class SlotMixin:
    """Base for a slot mix-in: plain Python, not a QObject (a QObject base would hide its slots from QML)."""


class Parts:
    """Mixed into DocBridge: the registry behind `handle` and `invoke`."""

    def handle(self, name: str, fn) -> None:
        if name in self._kit.handlers:
            raise RostrumError(codes.CONFLICT, "bridge", f'"{name}"', "already has a handler")
        self._kit.handlers[name] = fn

    def _invoke(self, name: str, args: list):
        fn = self._kit.handlers.get(name)
        if fn is None:
            self._fail(f'Error: invoke: no handler "{name}".')
            return None
        try:
            return fn(*args)
        except RostrumError as e:
            self._fail(e.line())
            return None
