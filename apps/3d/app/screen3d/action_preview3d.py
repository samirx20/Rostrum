"""The screen's side of Rostrum3D's action list (actions3d.py): one kit ActionHub (read in QML as `backend.actions`, with
the key map's jobs: key_routes3d.KeyHub3D) feeds the settings panel's actions, right-click (`menu()`), Ctrl+K's Do rows,
the keys, and hover preview. A slot mix-in for Bridge3D.

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

from .actions3d import LIST, Facts, bevel_fits
from .key_routes3d import KeyHub3D

PREVIEWABLE = {"combine.make", "camera.set"}     # a lens rested on shows through the camera


class ActionPreview3D:
    _previewed = None                    # the scratch copy's scene while a preview shows (screen state, never saved)

    def _make_actions(self):
        self._fits = {}                  # the engine's last bevel refusal: {item: largest bevel that fits} (actions3d.py)
        self._copied = ""                # the material Copy material took (screen state; Paste material makes the change)
        self._hub = KeyHub3D(self, LIST, self._facts3d, lambda f: self.selection_label(f.ids),
                             self._act_apply, self._act_do, self._set_status,
                             preview_fn=self._preview_calls, unpreview_fn=self._preview_end)
        self.selectedItemsChanged.connect(self._hub.refresh)
        self.docChanged.connect(self._hub.refresh)
        self._hub.refresh()

    def _facts3d(self) -> Facts:
        vp = getattr(self, "viewport", None)
        screen = {"copied": self._copied, "shot_id": self.shot_id, "can_shot": self.add.canAddShot,
                  "mode": vp.mode if vp is not None else "", "has_shot": vp.hasShot if vp is not None else False,
                  "pose": vp is not None and vp.pose_tool.on}
        return Facts(self.doc, list(self.selection), self._fits, screen)

    def engine_said(self, line: str) -> None:
        """The viewport's last engine answer ("" = a picture came): a bevel refusal offers the largest that fits."""
        fits = bevel_fits(line)
        if fits != self._fits:
            self._fits = fits
            self._hub.refresh()
            self._refresh()                  # the Bevel row's note and button follow

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
        if name == "clay-from" and getattr(self, "viewport", None) is not None:
            return self.viewport.clay_tool.turnIntoClay()  # clay_tool_qt.py: one clay.from_item, the new clay selected
        if name in ("pose-rest", "pose-find", "pose-names") and getattr(self, "viewport", None) is not None:
            p = self.viewport.pose_tool                     # pose_qt.py: one change each
            return p.rest() if name == "pose-rest" else p.findAgain() if name == "pose-find" else p.setNames(
                "plain" if p.names == "humanoid" else "humanoid")
        if name == "send-2d":
            return self.send_to.send(self.selected, "2d", "")          # send_qt.py: the scene sent to before, or the only one
        if name in ("duplicate", "delete"):
            return self.add.duplicate() if name == "duplicate" else self.add.remove()    # adding.py: one change, the copy picked
        if name == "copy-material":
            self._copied = self.doc.item(self.selected)["material"]
            self._hub.refresh()
            return self._set_status(f"Copied the material {self.label_of(self.doc.item(self._copied))}")
        if name == "paste-material":
            sel = self.selected
            return self._guard(lambda: self._done(self.doc.apply([self.edit_call(sel, "material", self._copied)], self.who,
                                                                 label="Paste material"), ""))
        if name == "lipsync":
            return self.open_lipsync(self.selected)
        vp = getattr(self, "viewport", None)
        if vp is not None and name == "look-through":
            return vp.setMode("light")
        if vp is not None and name == "link-lights":
            return vp.place.start("link", self.selected)
        if vp is not None and name == "shot-view":
            return vp.setMode("shot")
        if name == "new-shot":
            return self.newShotFromView()
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
