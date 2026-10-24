"""The right-click menu on the bridge: `entries` and `run` over context_menu.py's one list. Each run is the existing
operation (one undo step); a refusal fails loudly through the bridge. "Copy material" is screen state, never the document."""
from __future__ import annotations

from .context_menu import entries


class Context:
    def __init__(self, bridge):
        self.b, self.copied = bridge, ""

    def entries(self, item_id: str) -> list[dict]:
        b = self.b
        return entries(b.doc, item_id, {"copied": self.copied, "shot_id": b.shot_id, "can_shot": b.adder.canAddShot})

    def run(self, item_id: str, value: str):
        b = self.b
        if value not in [e["value"] for e in self.entries(item_id)]:
            return b.fail_line(f"Error: context menu: {value!r} doesn't apply to {item_id or 'empty space'} right now.")
        if item_id:
            b.select(item_id)
        if value == "duplicate":
            b.adder.duplicate()
        elif value == "delete":
            b.adder.remove()
        elif value == "link":
            b.viewport.place.start("link", item_id)
        elif value == "look":
            b.viewport.setMode("light")
        elif value == "home":
            b.viewport.home()
        elif value == "shot":
            b.adder.add("shot")
        elif value == "copy":
            self.copied = b.doc.item(item_id)["material"]
        elif value == "paste":
            b._guard(lambda: b._done(b.doc.apply([b.edit_call(item_id, "material", self.copied)], b.who,
                                                 label="Paste material"), ""))
