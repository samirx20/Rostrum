"""Lights placed and linked by clicking in the viewport (SPEC §7), through the operations agents use.

- **Place by highlight:** Alt+click a surface with a light selected: `light.place_highlight` moves and aims it so its
  highlight lands on the spot, seen from the viewport's camera. Right after Lights › Softbox (or any light) the next
  plain click does it too, at 4 × the item's size with the starting brightness (`brightness`).
- **Lights only:** "Pick what it lights" (right-click on a light): each click on an item adds it to the light's
  `lightsOnly`, a second click takes it out; Esc, or selecting something else, ends it.

The spot's surface direction comes from two more picks a few pixels to the right and below (highlight.normal_of): the
engine's pick answers a point, the same for the screen and for agents' `place_highlight`. Picks run on the viewport's
engine thread (ViewRenderer.call); the answer comes back to this thread as a signal, then one operation, one undo step.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from rostrum3d import aim, highlight as H, through

STEP = 3                                  # device pixels to the two neighbour picks


class PlaceLight(QObject):
    answered = Signal(object)             # (what, light id, result) from the engine thread

    def __init__(self, viewport):
        super().__init__(viewport)
        self.v, self.b = viewport, viewport.bridge
        self.mode, self.light = "", ""    # "place" (next click places a new light) | "link" (clicks set lightsOnly)
        self.answered.connect(self._apply)
        self.b.selectionChanged.connect(self._on_selection)

    # ---- entry points ----------------------------------------------------------------------------------------------
    def start(self, mode: str, light: str):
        self.mode, self.light = mode, light
        self.b.say(self.hint())

    def hint(self) -> str:
        if self.mode == "place":
            return "Click where its highlight should land  ·  Alt+click again later to move it"
        if self.mode == "link":
            on = self.b.doc.item(self.light).get("lightsOnly", "").split()
            return f"Lights only: {', '.join(on) or 'everything'}  ·  click items to add or take out  ·  Esc to finish"
        return ""

    def wants_click(self) -> bool:
        return bool(self.mode) and self.b.selected == self.light and self.b.doc.has(self.light)

    def click(self, x: float, y: float):
        """A plain click while placing or linking."""
        self._pick(x, y, self.mode, neighbours=self.mode == "place")

    def alt_click(self, x: float, y: float):
        sel = self.b.selected
        item = self.b.doc.item(sel) if sel else None
        if not item or item["type"] != "light" or item.get("kind", "rect") not in H.PLACEABLE:
            return self.b.fail_line("Error: place highlight: select a softbox, strip, bulb, spot or sun first, then Alt+click a surface.")
        self.light = sel
        self._pick(x, y, "move", neighbours=True)

    # ---- inside --------------------------------------------------------------------------------------------------
    def _on_selection(self, *_):
        if self.mode and self.b.selected != self.light:
            self.mode = ""
            self.b.say("")

    def _pick(self, x, y, what, neighbours):
        scene, cam = self.v._pick_at(x, y)
        light, frame = self.light, self.b.frame

        def job(eng):
            try:
                eng.ensure_scene(scene)
                hits = [eng.pick(**{**cam, "x": cam["x"] + dx, "y": cam["y"] + dy})
                        for dx, dy in ([(0, 0), (STEP, 0), (0, STEP)] if neighbours else [(0, 0)])]
                self.answered.emit((what, light, {"hits": hits, "scene": scene, "cam": cam, "frame": frame}))
            except Exception as e:                      # loud, on the status line (never a silent no-op)
                self.answered.emit(("error", light, str(e)))
        self.v._r.call(job)

    def _apply(self, answer):
        what, light, r = answer
        if what == "error":
            return self.b.fail_line(f"Error: {'lights only' if self.mode == 'link' else 'place highlight'}: {r}")
        first = r["hits"][0]
        if not first.get("hit"):
            return self.b.fail_line("Error: nothing there: click a surface of an item.")
        if what == "link":
            return self._toggle(light, first.get("item", ""))
        self._place(light, r, fresh=what == "place")

    def _place(self, light, r, fresh):
        hits = r["hits"]
        if not all(h.get("hit") and h.get("item") == hits[0]["item"] for h in hits):
            return self.b.fail_line("Error: place highlight: click inside a surface, not on its edge.")
        world, values, _ = through.find_item(r["scene"], r["cam"]["camera"], r["frame"]) if "camera" in r["cam"] else (None, None, None)
        eye = aim.point(world, [0.0, 0.0, 0.0]) if world else r["cam"]["eye"]
        points = [h["point"] for h in hits]
        try:
            normal = H.surface_normal(eye, hits)
            item_world, item_values, _ = through.find_item(r["scene"], hits[0]["item"], r["frame"])
        except ValueError as e:
            return self.b.fail_line(f"Error: place highlight: {e}")
        args = {"point": points[0], "normal": normal, "eye": eye}
        if fresh:
            args.update(distance=H.distance_for(H.item_size(item_world, item_values), eye, points[0]), brightness=True)
            self.mode = ""
        self.b._guard(lambda: self.b._done(self.b.doc.apply(
            [{"op": "light.place_highlight", "target": [light], "args": args}], self.b.who, label="Place highlight"), ""))
        self.b.say("")

    def _toggle(self, light, item):
        if item == light or not self.b.doc.has(item):
            return
        on = self.b.doc.item(light).get("lightsOnly", "").split()
        on = [i for i in on if i != item] if item in on else [*on, item]
        self.b._guard(lambda: self.b._done(self.b.doc.apply(
            [{"op": "light.set", "target": [light], "args": {"lightsOnly": " ".join(on)}}], self.b.who,
            label="Lights only"), ""))
        self.b.say(self.hint())
