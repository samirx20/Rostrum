"""Lip sync… in 3D (SPEC §9): right-click a mouth group › Lip sync…. The sheet is the kit's (rostrum_gui.lipsync_sheet,
qml/RostrumKit/LipSyncSheet.qml, shared with 2D); this is 3D's side: the mouth group the menu was opened on, its
children by name (rostrum3d.mouths), and Apply = one `lipsync.make` change (Visible keys on the shapes: on / off, held).
"""
from __future__ import annotations

from rostrum3d import mouths
from rostrum_gui.lipsync_sheet import LipSyncSheet as KitSheet


class Host:
    def __init__(self, bridge):
        self.b, self.target = bridge, ""

    @property
    def folder(self):
        return self.b.doc.folder

    def mouth(self):
        item = self.b.doc.item(self.target) if self.target and self.b.doc.has(self.target) else None
        if not item or not mouths.is_mouth(item):
            self.b._set_status("Lip sync needs a mouth: a group whose children are the mouth shapes.")
            return None
        return item["id"], item.get("name") or item["id"], [(c["id"], c.get("name") or c["id"]) for c in mouths.kids(item)]

    def apply(self, mouth, line, shapes) -> bool:
        call = {"op": "lipsync.make", "target": [mouth],
                "args": {"line": line["id"], **{f"shape{s}": child for s, child in shapes.items()}}}
        return self.b._guard(lambda: self.b._apply([call], f'Lip sync "{line["text"][:30]}"'))

    def fail(self, line):
        return self.b._fail(line)


def make(bridge):
    """(the sheet, open_for): open_for(group id) starts the sheet on that mouth."""
    host = Host(bridge)
    sheet = KitSheet(host)

    def open_for(item_id):
        host.target = item_id
        return sheet.start()
    return sheet, open_for
