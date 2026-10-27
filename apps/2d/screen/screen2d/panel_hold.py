"""A press that picks a layer and drags it at once moves it from the first frame: the new pick's settings panel (and the
timeline's scroll to its row, which follows the panel: LayerRows.qml) waits for the release, or for the pointer to rest
for about 0.1 s, so the drag's first frames don't build ~100 rows (6-45 ms at 200 layers, more on the first pick of a
session) before the layer moves. The kit's hook (bridge_select.holds_panel) holds it; this shows it when the hold ends.

A script's or an agent's pick isn't a person pointing (pointer_quiet): its panel comes at once, as before.
A slot mix-in for Bridge2D, ahead of DragSlots (whose hold, Alt+drag's many copies, still counts).
"""
from __future__ import annotations

from PySide6.QtCore import QTimer
from rostrum_gui import pointer_quiet
from rostrum_gui.parts import SlotMixin

LOOK_MS = 30            # how often a held panel checks whether its hold ended (the rest itself is pointer_quiet's 80 ms)


class PanelHold(SlotMixin):
    _hold_look = None   # the QTimer that looks, made on the first hold

    def holds_panel(self) -> bool:
        held = super().holds_panel() or (self._drag is not None and pointer_quiet.busy())
        if held:
            if self._hold_look is None:
                self._hold_look = QTimer(self, interval=LOOK_MS)
                self._hold_look.timeout.connect(self._hold_over)
            self._hold_look.start()
        return held

    def _hold_over(self):
        if not self._kit.panel_held:
            self._hold_look.stop()
        elif not self.holds_panel():          # released, or resting: the panel now
            self._hold_look.stop()
            self._show_panel()
