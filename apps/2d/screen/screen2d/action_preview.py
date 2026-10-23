"""Hover preview of an action (Figma's booleans, Keynote's alignment): while the pointer rests on Combine, Align, Distribute
or Mask in the settings panel, the canvas shows what the action would make, and goes back when the pointer leaves.

The action's own calls run on a scratch copy of the document (`run.plan`: pure, the live document and its history are
never touched) and that copy is described and drawn by the one engine path, like any frame (preview ≡ export): at
most half size, no motion blur, so it stays light. The picture is not the document: its tag is "preview", so the
overlays keep following the live document (shown.py), and anything that redraws the document (a change, the
playhead) ends it. An action that can't be previewed (not a previewable operation, a refusal, no picture) shows
nothing: no made-up result. A slot mix-in for Bridge2D."""
from __future__ import annotations

from rostrum_core import run
from rostrum_core.errors import RostrumError

from .action_rules import cutter_name

PREVIEW_TAG = ("preview",)
PREVIEWABLE = {"shape.boolean", "layer.align", "layer.distribute", "mask.make"}   # what the panel's Combine, Align, Distribute, Mask run
PREVIEW_SCALE = 0.5


class ActionPreview:
    _previewing = False
    _preview_status = ""

    def _preview_calls(self, calls) -> None:
        """Draw `calls` as they would leave the document, without applying them."""
        if not calls or self.play.playing or self.dragging() or not {c["op"] for c in calls} <= PREVIEWABLE:
            return
        from rostrum2d.scene import describe
        try:
            work = run.plan(self.doc.kind, self.doc.data, calls, self.doc.locked_by, self.who)[0]
            scene = describe(work, self.comp_id, self.marks.times, self.doc.folder, (0.0, self.comp()["duration"]))
        except RostrumError:
            return                                              # the action is refused now: nothing to show
        cut = next((c for c in calls if c["op"] == "mask.make"), None)
        if cut and not self._previewing:                        # a Mask: say which layer is the cutter, until the pointer leaves
            self._preview_status = self.status
            self._set_status(f"Mask preview — {cutter_name(cut, self.doc)} is the cutter (the top layer)")
        self._previewing = True
        self.frames.request(scene, self._t, 1, min(self._view, PREVIEW_SCALE), PREVIEW_TAG)

    def _preview_end(self) -> None:
        """The pointer left: the canvas goes back to the document (a no-op when no preview is showing)."""
        if self.status.startswith("Mask preview"):             # the cutter's words go with it
            self._set_status(self._preview_status)
        if self._previewing:
            self._show()
