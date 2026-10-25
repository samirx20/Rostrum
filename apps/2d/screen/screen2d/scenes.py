"""Scenes on the screen (a slot mix-in for Bridge2D, see rostrum_gui/parts.py): which scene the window shows, and New scene.
Showing another scene is screen state, never an edit (like the tool or the playhead): its layers, its length, its frame
size and its picture replace the last one's, nothing is picked, the playhead keeps its time as far as the scene lasts.
New scene = comp.add (one change: Undo takes it away), sized and timed like the scene shown so a cut between them
matches, then shown. The crumb after the project's name (Main.qml › SceneCrumb.qml) is the one control; it lists the
scenes and ends with New scene. Copy a layer in one scene, show another, Paste: clipboard.py does the rest (a layer
carries its own settings, so it works across scenes and projects alike).
"""
from __future__ import annotations

from PySide6.QtCore import Slot
from rostrum2d.names import display_name
from rostrum_gui.parts import SlotMixin

NEW = "+scene"
LIKE = ("width", "height", "fps", "duration", "background")      # a new scene starts like the one shown


class SceneSlots(SlotMixin):
    @Slot(result="QVariantList")
    def sceneEntries(self):
        """The crumb's list: every scene (the shown one checked), then New scene."""
        rows = [{"value": c["id"], "label": display_name(c), "checked": c["id"] == self.comp_id}
                for c in self.doc.data.get("comps", [])]
        return rows + [{"value": NEW, "label": "New scene"}]

    @Slot(str)
    def showScene(self, scene_id):
        """Show another scene (screen state, not an edit). `NEW` makes one first."""
        if scene_id == NEW:
            return self.newScene()
        if not scene_id or scene_id == self.comp_id:
            return
        if not any(c["id"] == scene_id for c in self.doc.data.get("comps", [])):
            return self._fail(f'Error: scene: no scene "{scene_id}".')
        self.play.stop()
        self.endDrag()
        self.comp_id, self._comp_at = scene_id, None
        self.select(scene_id)
        self.exporter.setComp(scene_id)                  # Export shows the scene you are looking at
        self.setTime(self._t)                            # clamped to the new scene's length; rows, outline, picture
        self._render_all()

    @Slot()
    def newScene(self):
        """A new scene like this one (one change), shown at once."""
        before = {c["id"] for c in self.doc.data.get("comps", [])}
        here = self.comp()
        args = {k: here[k] for k in LIKE if k in here}
        if self._guard(lambda: self._apply([{"op": "comp.add", "args": args}], "New scene")):
            made = [c["id"] for c in self.doc.data.get("comps", []) if c["id"] not in before]
            if made:
                self.showScene(made[0])

    def scene_still_there(self):
        """The scene shown was taken away (Undo of New scene, a deleted scene): the first one is shown instead."""
        if not self.doc.has(self.comp_id):
            self.comp_id, self._comp_at = self.doc.data["comps"][0]["id"], None
            self._t = 0.0
            self.exporter.setComp(self.comp_id)
