"""What an agent's change looks like on the 2D screen: where a changed item sits (for the 1-second outline) and the
harmless calls the layout check's `agent-run n` makes. A slot mix-in for Bridge2D."""
from __future__ import annotations

from PySide6.QtCore import Slot
from rostrum2d import fields as F
from rostrum_gui.parts import SlotMixin

from . import bounds


class AgentView(SlotMixin):
    @Slot(str, result="QVariantMap")
    def rectOf(self, item_id):
        """The box on the canvas, in composition px ({x, y, w, h, rot, ax, ay}), of the layer an item belongs to
        (an effect, mask or key counts as its layer); {} when it has none showing now (gone, hidden, out of time)."""
        if not self.doc.has(item_id):
            return {}
        layer = bounds.layer_of(self.doc, item_id)
        return next((b for b in self.shown_boxes() if b["id"] == layer), {})

    def agent_demo_calls(self, n):
        """n lists of calls, each moving the first layer 10 px further to the right (the layout check's `agent-run`)."""
        layer = next(l for l in self.comp()["layers"] if l["type"] in F.LAYERS and l["type"] not in ("camera", "group"))
        x = self.doc.item(layer["id"]).get("x", 0)
        return [[{"op": f"{layer['type']}.set", "target": [layer["id"]], "args": {"x": x + 10 * (i + 1)}}] for i in range(n)]
