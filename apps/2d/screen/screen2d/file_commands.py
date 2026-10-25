"""Ctrl+K and the file actions: New, Open, Duplicate … join the command bar's list (the kit's ProjectFiles says
which apply now: rostrum_gui/file_menu.py). The Add commands are the Add menu's own entries (adding.py: a picture asks
for its file, a 3D render only for a rendered 3D item), never a bare `layer.add` that would make an empty layer.
A slot mix-in for Bridge2D."""
from __future__ import annotations

from PySide6.QtCore import Slot
from rostrum_gui.parts import SlotMixin


class FileCommands(SlotMixin):
    files = None                                    # set by session.py: the kit's ProjectFiles

    def _commands(self):
        out = [c for c in super()._commands() if not c["key"].startswith("layer.add:")]
        files = [{**c, "weight": 1} for c in self.files.commands()] if self.files else []   # an action on the picked layer
        return files + self._adder.commands() + out                                      # wins a tie: "dupl" → Duplicate

    @Slot(str, result=bool)
    def run(self, key):
        if self.files and key.startswith("file:"):
            self.files.pickLater(key)           # New, Open, Open recent swap the whole screen: after the bar's own handler ends
            return True
        return super().run(key)
