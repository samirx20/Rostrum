"""What follows the outline after a document change or a pick, told the frame after (the kit's after_frame.py): the
timeline's rows, the panels that read the selected layer, the key bar, the pen, the painter's target, the frame's box.
The change itself (the document, the picture asked of the engine) and the pick's own highlight come first, in the
frame of the click; told inside it, Ctrl+G or a shape's release ran all of these too (~20-40 ms in one frame).
A change elsewhere (an agent's, an undo) that leaves the selection alone tells only the timeline's rows."""
from __future__ import annotations

from rostrum_gui.after_frame import AfterFrame


class OutlineNews:
    def __init__(self, bridge):
        self.b, self._reached = bridge, False
        self._job = AfterFrame(self._tell, bridge)

    def soon(self, reached: bool = True):
        """Tell it the frame after (`reached`: the selection's own outline changed, else only the rows)."""
        self._reached = self._reached or reached
        self._job.ask()

    def now(self):
        """A reader that needs it told already (it is told at once)."""
        self._job.flush()

    def cancel(self):
        self._job.cancel()
        self._reached = False

    def _tell(self):
        reached, self._reached = self._reached, False
        self.b.outlineChanged.emit() if reached else self.b._layers_check()
