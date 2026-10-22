"""Slots and handlers for a bridge that live outside the bridge class (no Qt object of their own).

Three ways, from the lightest; each leaves the existing bridges as they are:
- A slot mix-in: a plain class (no base) whose methods carry `@Slot`. List it before DocBridge in the bridge's
  bases and QML sees its slots as the bridge's own: `class Bridge2D(ZoomSlots, DocBridge)`. The mix-in reaches the
  bridge through `self` (`self.doc`, `self.who`, `self._apply`, `self._guard`). `SlotMixin` below only names the idea.
- `bridge.attach("pen", Pen(self))`: a QObject with its own slots and properties, read in QML as `bridge.pen`
  (the old way, `@Property(QObject, constant=True)`, written once for every part).
- `bridge.handle("zoomTo", fn)`: a Python function registered by name from any module; QML calls
  `bridge.invoke("zoomTo", [args])`. A handler that raises RostrumError is reported, never swallowed (like an edit).
"""
from __future__ import annotations

from rostrum_core import RostrumError, codes


class SlotMixin:
    """Base for a slot mix-in: plain Python, not a QObject (a QObject base would hide its slots from QML)."""


class Parts:
    """Mixed into DocBridge: the registry behind `attach`, `handle` and `invoke`."""

    def attach(self, name: str, obj) -> None:
        """Offer `obj` (a QObject) to QML as `bridge.<name>`."""
        if self.property(name) is not None:
            raise RostrumError(codes.CONFLICT, "bridge", f'"{name}"', "is already a property of the bridge")
        self.setProperty(name, obj)                  # a dynamic property: the bridge class stays untouched

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
