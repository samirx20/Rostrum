"""A camera's focus set by clicking in the viewport (SPEC §8, Job e), through the operations agents use.

With a camera selected and its depth of field on, the settings panel offers **Focus on a point** and **Focus on an
item** (actions3d.py). The next click in the viewport picks through the engine (the same pick as selecting):
- a point: `camera.set focusDistance` = how far in front of the camera (along its −Z, as a lens measures) the clicked
  spot is, and focusItem cleared (a picked distance stays put);
- an item (or Alt+click while picking a point): `camera.set focusItem` = the item clicked; the compiler then works the
  distance out every frame, so the focus follows it as it moves.
One click, one operation, one undo step. Esc, or selecting something else, stops picking.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from rostrum3d import aim, through


class FocusPick(QObject):
    answered = Signal(object)             # (camera, on_item, pick answer or error line) from the engine thread

    def __init__(self, viewport):
        super().__init__(viewport)
        self.v, self.b = viewport, viewport.bridge
        self.camera, self.on_item = "", False
        self.answered.connect(self._apply)
        self.b.selectionChanged.connect(self._on_selection)

    def start(self, camera: str, on_item: bool):
        self.camera, self.on_item = camera, on_item
        self.b.say("Click the item to keep sharp  ·  Esc to stop" if on_item
                   else "Click where it should be sharp  ·  Alt+click to follow an item  ·  Esc to stop")

    def stop(self):
        if self.camera:
            self.camera = ""
            self.b.say("")

    def wants_click(self) -> bool:
        return bool(self.camera) and self.b.selected == self.camera and self.b.doc.has(self.camera)

    def click(self, x: float, y: float, on_item: bool = False):
        scene, cam = self.v._pick_at(x, y)
        camera, item_mode, frame = self.camera, on_item or self.on_item, self.b.frame
        self.camera = ""                                    # one click sets it

        def job(eng):
            try:
                eng.ensure_scene(scene)
                self.answered.emit((camera, item_mode, {"hit": eng.pick(**cam), "frame": frame}))
            except Exception as e:                          # loud, on the status line (never a silent no-op)
                self.answered.emit((camera, item_mode, str(e)))
        self.v._r.call(job)

    def _on_selection(self, *_):
        if self.camera and self.b.selected != self.camera:
            self.stop()

    def _apply(self, answer):
        camera, on_item, r = answer
        if isinstance(r, str):
            return self.b.fail_line(f"Error: focus: {r}")
        hit = r["hit"]
        if not hit.get("hit") or not self.b.doc.has(camera):
            return self.b.fail_line("Error: focus: nothing there: click a surface of an item.")
        if on_item:
            if hit.get("item") == camera or not self.b.doc.has(hit.get("item", "")):
                return self.b.fail_line("Error: focus: click an item of the scene to keep sharp.")
            calls, label = [{"op": "camera.set", "target": [camera], "args": {"focusItem": hit["item"]}}], "Focus on item"
        else:
            world = through.find_item(self.v._compiled(), camera, r["frame"])[0]
            d = aim.ahead(world, hit["point"])
            if d <= 0:
                return self.b.fail_line("Error: focus: that spot is behind the camera; click something it sees.")
            calls = ([{"op": "camera.set", "target": [camera], "args": {"focusItem": ""}}]
                     if self.b.doc.item(camera).get("focusItem") else [])
            calls.append(self.b.edit_call(camera, "focusDistance", round(d, 4)))
            label = "Focus"
        self.b._guard(lambda: self.b._done(self.b.doc.apply(calls, self.b.who, label=label), ""))
        self.b.say("")
