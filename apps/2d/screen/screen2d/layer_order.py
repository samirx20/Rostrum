"""Layer order and removal on screen: Bring forward / Send backward / Bring to front / Send to back (Ctrl+] / Ctrl+[,
with Shift for the ends), Delete layer (the Delete key) and Rename layer (F2, or double-click in the Layers panel).
They join Ctrl+K's list, each only while it can apply (a top layer has no Bring forward). Each is the operations an
agent calls (layer.arrange, layer.remove, item.rename) in one batch = one undo step. A slot mix-in for Bridge2D."""
from __future__ import annotations

from PySide6.QtCore import Slot
from rostrum_gui.parts import SlotMixin

ORDER = {"front": ("Bring to front", "Ctrl+Shift+]"), "forward": ("Bring forward", "Ctrl+]"),
         "backward": ("Send backward", "Ctrl+["), "back": ("Send to back", "Ctrl+Shift+[")}


def reordered(stack: list[str], picked: set[str], how: str) -> list[str]:
    """The stack (index 0 = bottom) after moving the picked layers; their order among themselves stays."""
    mine = [i for i in stack if i in picked]
    rest = [i for i in stack if i not in picked]
    if how == "front":
        return rest + mine
    if how == "back":
        return mine + rest
    out, step = list(stack), (1 if how == "forward" else -1)
    for i in (reversed(range(len(out))) if step > 0 else range(len(out))):
        j = i + step
        if out[i] in picked and 0 <= j < len(out) and out[j] not in picked:
            out[i], out[j] = out[j], out[i]
    return out


def arrange_calls(doc, layers: list[str], how: str) -> list[dict]:
    """layer.arrange calls that put each parent's stack in the new order (none when nothing would move)."""
    calls, by_parent = [], {}
    for layer in layers:
        by_parent.setdefault(doc.parent_of(layer)[0], set()).add(layer)
    for parent, picked in by_parent.items():
        now = [c["id"] for c in doc.item(parent)["layers"]]
        new = reordered(now, picked, how)
        for i, id_ in enumerate(new):
            if now[i] != id_:
                calls.append({"op": "layer.arrange", "target": [id_], "args": {"index": i}})
                now.remove(id_)
                now.insert(i, id_)
    return calls


class LayerOrder(SlotMixin):
    # Bridge2D has `renameRequested = Signal(str)`: the Layers panel opens its name box for that layer

    def _selected_layers(self) -> list[str]:
        return [i for i in self._multi.layers() if self.doc.has(i) and self.doc.item(i)["type"] in self._layer_types()]

    def _layer_types(self):
        return self.doc.kind.registry.get("layer.remove").targets

    def _layer_commands(self) -> list[dict]:
        layers = self._selected_layers()
        if not layers:
            return []
        out = []
        for how, (label, keys) in ORDER.items():
            calls = arrange_calls(self.doc, layers, how)
            if calls:
                out.append({"key": f"layer:{how}", "label": label, "hint": f"Layer order ({keys})", "calls": calls})
        out.append({"key": "layer:delete", "label": "Delete layer" + ("s" if len(layers) > 1 else ""), "hint": "Layer (Delete)",
                    "calls": [{"op": "layer.remove", "target": layers, "args": {}}]})
        if len(layers) == 1:
            out.append({"key": "layer:rename", "label": "Rename layer", "hint": "Layer (F2)", "rename": layers[0]})
        return out

    def _commands(self):
        out = [c for c in super()._commands() if c["key"] != "layer.remove"]       # "Delete layer" below says it better
        return self._layer_commands() + out

    @Slot(str, result=bool)
    def run(self, key):
        if key == "layer:rename" and any(c["key"] == key for c in self._layer_commands()):
            self.renameRequested.emit(self._selected_layers()[0])
            return True
        return super().run(key)

    @Slot(str, str, result=bool)
    def renameLayer(self, layer_id, name):
        """The Layers panel's name box: item.rename, one change (an empty name changes nothing)."""
        name = name.strip()
        if not name or name == self.doc.item(layer_id).get("name"):
            return False
        return self._guard(lambda: self._apply([{"op": "item.rename", "target": [layer_id], "args": {"name": name}}],
                                               f"Rename {self.label_of(self.doc.item(layer_id))}"))

    @Slot(str, result=bool)
    def layerCommand(self, how):
        """A shortcut's command (front, back, forward, backward, delete, rename): the same as Ctrl+K's, and quiet when it
        can't apply right now."""
        if not any(c["key"] == f"layer:{how}" for c in self._layer_commands()):
            return False
        return self.run(f"layer:{how}")
