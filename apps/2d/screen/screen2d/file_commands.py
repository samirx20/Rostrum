"""Ctrl+K and the file actions: New, Open, Duplicate … join the command bar's list (the kit's ProjectFiles says
which apply now: rostrum_gui/file_menu.py), and
the Add commands leave out 3D render layers when Rostrum3D is not installed. A slot mix-in for Bridge2D."""
from __future__ import annotations

from PySide6.QtCore import Slot
from rostrum2d import settings
from rostrum_gui.parts import SlotMixin

ONLY_WITH_3D = {"layer.add:render3d"}


class FileCommands(SlotMixin):
    files = None                                    # set by session.py: the kit's ProjectFiles

    def _commands(self):
        out = super()._commands()
        if not settings.has_rostrum3d():
            out = [c for c in out if c["key"] not in ONLY_WITH_3D]
        return (self.files.commands() if self.files else []) + out

    @Slot(str, result=bool)
    def run(self, key):
        if self.files and key.startswith("file:"):
            return self.files.pick(key)
        return super().run(key)
