"""Scenes on the screen (a slot mix-in for Bridge2D, see rostrum_gui/parts.py): which scene the window shows, and New scene,
Rename, Duplicate, Move earlier / later and Delete (the operations agents call too: comp.add, item.rename,
comp.duplicate, comp.move, comp.remove). `showScene` is the ONE route that shows a scene: the crumb, Ctrl+K (Select
<scene>, New scene) and every screen path that makes or picks a scene go through it, so picking a scene always shows it.
Delete asks nothing: Undo is the safety, and the top bar says so.
Showing another scene is screen state, never an edit (like the tool or the playhead): its layers, its length, its frame
size and its picture replace the last one's, nothing is picked, the playhead keeps its time as far as the scene lasts.
New scene = comp.add (one change: Undo takes it away), sized and timed like the scene shown so a cut between them
matches, then shown. The crumb after the project's name (Main.qml > SceneCrumb.qml) is the one control; its menu lists
the scenes and what can be done with the one shown. Copy a layer in one scene, show another, Paste: clipboard.py does the
rest (a layer carries its own settings, so it works across scenes and projects alike).
"""
from __future__ import annotations

from PySide6.QtCore import Slot
from rostrum2d.names import display_name
from rostrum_gui.parts import SlotMixin

NEW = "+scene"
LIKE = ("width", "height", "fps", "duration", "background")      # a new scene starts like the one shown
ROUTES = {"comp.add": "newScene", "comp.remove": "deleteScene", "comp.duplicate": "duplicateScene"}   # Ctrl+K's keys


class SceneSlots(SlotMixin):
    _shown_before: list = []                              # the scenes shown before this one, newest last (Undo falls back to them)

    def _scenes(self) -> list[dict]:
        return self.doc.data.get("comps", [])

    @Slot(result="QVariantList")
    def sceneEntries(self):
        """The crumb's menu: every scene (the shown one checked), then what can be done with the scene shown. Only what
        applies is there: no Delete for the last scene, no Move earlier for the first."""
        scenes = self._scenes()
        at = next((n for n, c in enumerate(scenes) if c["id"] == self.comp_id), 0)
        rows = [{"value": c["id"], "label": display_name(c), "checked": c["id"] == self.comp_id} for c in scenes]
        rows += [{"value": NEW, "label": "New scene"}, {"value": "scene:rename", "label": "Rename scene"},
                 {"value": "scene:duplicate", "label": "Duplicate scene"}]
        if at > 0:
            rows.append({"value": "scene:earlier", "label": "Move scene earlier"})
        if at < len(scenes) - 1:
            rows.append({"value": "scene:later", "label": "Move scene later"})
        if len(scenes) > 1:
            rows.append({"value": "scene:delete", "label": "Delete scene"})
        return rows

    @Slot(str)
    def sceneMenuPicked(self, value):
        """A pick in the crumb's menu: a scene to show, New scene, or an action on the scene shown (Rename is the
        crumb's own name box, SceneCrumb.qml)."""
        verbs = {"scene:duplicate": self.duplicateScene, "scene:delete": self.deleteScene,
                 "scene:earlier": lambda: self.moveScene(-1), "scene:later": lambda: self.moveScene(1)}
        if value in verbs:
            verbs[value]()
        elif value != "scene:rename":
            self.showScene(value)

    @Slot(str)
    def showScene(self, scene_id):
        """Show another scene (screen state, not an edit). `NEW` makes one first."""
        if scene_id == NEW:
            return self.newScene()
        if not scene_id or scene_id == self.comp_id:
            return
        if not any(c["id"] == scene_id for c in self._scenes()):
            return self._fail(f'Error: scene: no scene "{scene_id}".')
        self.play.stop()
        self.endDrag()
        self._shown_before = [*self._shown_before, self.comp_id][-20:]
        self.comp_id, self._comp_at = scene_id, None
        self.select(scene_id)
        self.exporter.setComp(scene_id)                  # Export shows the scene you are looking at
        self.setTime(self._t)                            # clamped to the new scene's length; rows, outline, picture
        self._render_all()

    def _made_then_show(self, calls, label):
        """Apply a change that makes a scene (one change), then show the new scene."""
        before = {c["id"] for c in self._scenes()}
        if self._guard(lambda: self._apply(calls, label)):
            made = [c["id"] for c in self._scenes() if c["id"] not in before]
            if made:
                self.showScene(made[0])

    @Slot()
    def newScene(self):
        """A new scene like this one (one change), shown at once."""
        here = self.comp()
        self._made_then_show([{"op": "comp.add", "args": {k: here[k] for k in LIKE if k in here}}], "New scene")

    @Slot()
    def duplicateScene(self):
        """A copy of the scene shown, right after it (one change), shown at once."""
        self._made_then_show([{"op": "comp.duplicate", "target": self.comp_id, "args": {}}], "Duplicate scene")

    @Slot(str)
    def renameScene(self, name):
        """Rename the scene shown (one change). An empty name changes nothing."""
        name = name.strip()
        if name and name != self.comp().get("name"):
            self._guard(lambda: self._apply([{"op": "item.rename", "target": self.comp_id, "args": {"name": name}}],
                                            "Rename scene"))

    @Slot(int)
    def moveScene(self, step):
        """The scene shown, one place earlier (-1) or later (+1) in the list (one change)."""
        ids = [c["id"] for c in self._scenes()]
        to = ids.index(self.comp_id) + step
        if 0 <= to < len(ids):
            self._guard(lambda: self._apply([{"op": "comp.move", "target": self.comp_id, "args": {"index": to}}],
                                            "Move scene earlier" if step < 0 else "Move scene later"))

    @Slot()
    def deleteScene(self):
        """Delete the scene shown (one change; no question: Undo brings it back, and the top bar says so). The scene
        next to it shows instead."""
        scenes = self._scenes()
        if len(scenes) < 2:
            return self._fail("Error: scene: a project needs at least one scene.", "A project needs at least one scene.")
        gone = display_name(self.comp())
        at = next(n for n, c in enumerate(scenes) if c["id"] == self.comp_id)
        near = scenes[at - 1 if at else 1]["id"]
        was, self._shown_before = self._shown_before, [*self._shown_before, near]    # (the change's own event shows `near`)
        if self._guard(lambda: self._apply([{"op": "comp.remove", "target": self.comp_id, "args": {}}], "Delete scene")):
            self._render_all()
            self.say(f"Deleted {gone} — Ctrl+Z brings it back")
        else:
            self._shown_before = was

    @Slot(str, result=bool)
    def run(self, key):
        """Ctrl+K: a scene's own commands go through the scene routes above, like the crumb's menu."""
        if key.startswith("select:") and any(c["id"] == key[7:] for c in self._scenes()):
            self.showScene(key[7:])
            return True
        if key in ROUTES:
            getattr(self, ROUTES[key])()
            return True
        return super().run(key)

    def scene_still_there(self):
        """The scene shown was taken away (Undo of New scene, a deleted scene): the one shown before it shows instead
        (the first when none of them is left)."""
        if self.doc.has(self.comp_id):
            return
        back = next((i for i in reversed(self._shown_before) if self.doc.has(i)), self._scenes()[0]["id"])
        self._shown_before = [i for i in self._shown_before if i != back]
        self.comp_id, self._comp_at = back, None
        self._t = 0.0
        self.exporter.setComp(back)
