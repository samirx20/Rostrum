"""An app's list of feature modules as data: the operation modules its document kind loads, the tool modules its agent
server loads. Each app keeps its lists in one `modules.py` (apps/<app>/.../modules.py); a plugin adds to the same list
through `add`, so a built-in and a plugin's module are loaded one way.

    OPS = ModuleList("rostrum2d", [".ops_draw", ".ops_items", ".rig.ops"])      # relative to the package
    OPS.load()                          # imports each in order; an operation module registers when imported
    TOOLS.attrs("tools")                # each module's `tools`, in order
    TOOLS.call("register", tools)       # calls each module's `register(tools)`, in order

Order is the order of registration, so it is the order agents see; `add` appends. A module that fails to import
raises (loud): a half-loaded app is a bug, never a quiet gap.
"""
from __future__ import annotations

import importlib
from types import ModuleType


class ModuleList:
    def __init__(self, package: str, names=(), origin: str = "builtin"):
        self.package = package
        self._entries: list[tuple[str, str]] = [(n, origin) for n in names]

    def add(self, name: str, origin: str) -> None:
        """Append a module (a plugin's, by its absolute dotted name). Its origin is the plugin's id."""
        if (name, origin) not in self._entries:
            self._entries.append((name, origin))

    @property
    def names(self) -> list[str]:
        return [n for n, _ in self._entries]

    def origin(self, name: str) -> str:
        return next(o for n, o in self._entries if n == name)

    def load(self) -> list[ModuleType]:
        return [importlib.import_module(n, self.package) for n, _ in self._entries]

    def attrs(self, attr: str) -> list:
        return [getattr(m, attr) for m in self.load()]

    def call(self, fn: str, *args) -> None:
        for m in self.load():
            getattr(m, fn)(*args)
