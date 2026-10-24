"""The screen's side of Rostrum3D's action list (actions3d.py): one kit ActionHub (read in QML as `backend.actions`)
feeds the settings panel's actions, and hover preview. A slot mix-in for Bridge3D.

Hover preview (2D's ActionPreview, same idea): while the pointer rests on Combine's Union, Subtract or Intersect (or a lens), the
viewport shows the result. The action's calls run on a scratch copy of the document (`run.plan`: pure, the live document
and its history are never touched); that copy is described and drawn by the one engine path like any frame (preview ≡
export). The preview is held in `self._previewed` and handed out by `scene()`; the pointer leaving, or any document
change, drops it and the live document is drawn again. An action that can't be previewed (a refusal, no picture)
shows nothing: no made-up result.
"""
from __future__ import annotations

from rostrum3d.compile import describe
from rostrum_core import run
from rostrum_core.errors import RostrumError
from rostrum_gui.action_hub import ActionHub

from .actions3d import LIST, Facts, bevel_fits

PREVIEWABLE = {"combine.make", "camera.set"}     # a lens rested on shows through the camera


class ActionPreview3D:
    _previewed = None                    # the scratch copy's scene while a preview shows (screen state, never saved)

    def _make_actions(self):
        self._fits = {}                  # the engine's last bevel refusal: {item: largest bevel that fits} (actions3d.py)
        self._hub = ActionHub(LIST, lambda: Facts(self.doc, list(self.selection), self._fits), lambda f: self.selection_label(f.ids),
                              self._act_apply, self._act_do, self._set_status, self,
                              preview_fn=self._preview_calls, unpreview_fn=self._preview_end)
        self.selectedItemsChanged.connect(self._hub.refresh)
        self.docChanged.connect(self._hub.refresh)
        self._hub.refresh()

    def engine_said(self, line: str) -> None:
        """The viewport's last engine answer ("" = a picture came): a bevel refusal offers the largest that fits."""
        fits = bevel_fits(line)
        if fits != self._fits:
            self._fits = fits
            self._hub.refresh()

    def _act_apply(self, calls, label):
        """An action's calls as one change; what it made is selected after."""
        self._preview_end()
        made = [c["args"]["id"] for c in calls if c["op"] == "combine.make"]
        self._guard(lambda: self._apply(calls, label))
        if made and self.doc.has(made[0]):
            self.select(made[0])

    def _act_do(self, name, entry):
        if name == "edit-mesh" and getattr(self, "viewport", None) is not None:
            return self.viewport.mesh_edit.enter()          # Edit mesh is screen state (mesh_edit_qt.py)
        if name in ("focus-point", "focus-item") and getattr(self, "viewport", None) is not None:
            return self.viewport.focus.start(self.selected, name == "focus-item")   # the next click (focus_pick.py)
        raise ValueError(f'action {entry["id"]}: Rostrum3D has no "{name}" action')

    def _preview_calls(self, calls) -> None:
        """Draw `calls` as they would leave the document, without applying them."""
        if self.playing or self._mover.active or not calls or not {c["op"] for c in calls} <= PREVIEWABLE:
            return
        try:
            work = run.plan(self.doc.kind, self.doc.data, calls, self.doc.locked_by, self.who)[0]
            self._previewed = describe(work, self.shot_id, self.doc.folder)
        except RostrumError:
            return                                              # refused now: nothing to show
        self._redraw_viewport()

    def _preview_end(self) -> None:
        """The pointer left (or something changed): the viewport goes back to the document (no-op when none shows)."""
        if self._previewed is not None:
            self._previewed = None
            self._redraw_viewport()

    def _redraw_viewport(self) -> None:
        vp = getattr(self, "viewport", None)
        if vp is not None:
            vp._on_doc()                 # the viewport compiles the scene again (scene() says which) and draws it
