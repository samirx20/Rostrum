"""Lip sync… on a mouth swap set (UX_SPEC 3.23; `backend.lipsync`): the one sheet is the kit's (rostrum_gui.lipsync_sheet,
qml/RostrumKit/LipSyncSheet.qml, shared with 3D); this is 2D's side of it: which swap set is selected, its drawings by
name (rig_mouths.py), and Apply = one `lipsync.apply` change (keys on the set's Shows, held per sound).
"""
from __future__ import annotations

from rostrum2d.names import display_name
from rostrum_gui.lipsync_sheet import LipSyncSheet as KitSheet


class Host:
    def __init__(self, bridge):
        self.b = bridge

    @property
    def folder(self):
        return self.b.doc.folder

    def mouth(self):
        sel = self.b.selected_layers()
        item = self.b.doc.item(sel[0]) if len(sel) == 1 else None
        if not item or not item.get("swap"):
            self.b._set_status("Lip sync needs one swap set of mouth drawings selected.")
            return None
        return item["id"], display_name(item), [(k["id"], display_name(k)) for k in item.get("layers", [])]

    def apply(self, mouth, line, shapes) -> bool:
        args = {"source": line["file"], "at": line["at"], **({"text": line["text"]} if line["english"] else {}),
                **{f"shape{s}": lay for s, lay in shapes.items()}}
        call = {"op": "lipsync.apply", "target": [mouth], "args": args}
        return self.b.guard(lambda: self.b._apply([call], f'Lip sync "{line["text"][:30]}"'))

    def fail(self, line):
        return self.b._fail(line)


def LipSyncSheet(bridge):
    return KitSheet(Host(bridge))
