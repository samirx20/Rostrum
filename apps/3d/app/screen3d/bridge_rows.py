"""The settings panel's rows for Bridge3D (a slot mix-in): the kit's rows with the data groups left out, the Final tags,
a field that names another item shown as a choice, and facts_of: the SCREEN's facts added to the kind's (`animating`: a
setting valid only while animating shows only on the Animate page; agents have no pages, so for them it always holds)."""
from __future__ import annotations

from rostrum3d import fields as F

from .actions3d import fit_note
from .materials import USERS

FINAL_TIP = "Shows in Final, not in the Quick view"
APPROX_TIP = "Shows fully in Final; the Quick view only hints at it"
NONE_FIRST = {"material", "item"}       # fields naming another item that may name none ("" = no material, focus on a distance)
DATA_GROUPS = F.DATA_GROUPS              # data an operation writes (a mesh's points, a bone's head), never rows


def _is_data(type_, r) -> bool:
    p = F.param(type_, r["id"]) if r.get("row") == "param" else None
    return (p is not None and p.group in DATA_GROUPS) or any(r.get(k) in DATA_GROUPS for k in ("group", "in", "fold"))


def _without_data(r):
    names = r.get("names")
    return {**r, "names": [n for n in names if n.get("group") not in DATA_GROUPS]} if isinstance(names, list) else r


class RowsMixin:
    FINAL_ONLY: dict = {}               # set by Bridge3D: fields the quick view can't show
    QUICK_APPROX: dict = {}             # set by Bridge3D: fields the quick view only hints at

    def facts_of(self, item: dict) -> dict:
        """The kind's facts and what only the screen knows (the same names agents' facts carry): `animating`, so a
        setting valid only while animating shows only on the Animate page; `sculpting`, so a clay's Brush group shows
        only while the Clay tool is on."""
        return {**self.doc.kind.facts(item, self.doc), "animating": self._page == "animate",
                "sculpting": self._sculpting()}

    def _sculpting(self) -> bool:
        tool = getattr(getattr(self, "viewport", None), "clay_tool", None)
        return bool(tool is not None and tool.on)

    def rows_context(self):
        """What the rows read that no document change announces (the kit's kept rows are worked out again when it
        differs): the page (`animating`), the Clay tool (`sculpting`), the shot shown and the playhead (values are
        shown at the playhead)."""
        return self._page, self._sculpting(), getattr(self, "shot_id", None), getattr(self, "_frame", None)

    def on_page(self, item):
        """An item's material shows in its own Material row (MaterialRow.qml, the picker), not as a plain choice."""
        return {"material"} if item.get("type") in USERS else set()

    def _rows(self):
        """The inspector's rows, with a field that names another item (its `kind`: a mesh's material, a shot's camera)
        shown as a choice of those items by name. Still the same field, written through the same operation."""
        from . import outline
        rows = super()._rows()
        if not self._sel:
            return rows
        type_, doc_items = self.doc.item(self._sel)["type"], None
        rows = [_without_data(r) for r in rows if not _is_data(type_, r)]     # an editable mesh's points: data, not controls
        buttons = self._hub.row_buttons() if hasattr(self, "_hub") else {}               # actions that sit on a row (Action.row): Lens, Focus on an item, bevel
        for r in rows:
            if r["row"] == "param":
                r["button"] = buttons.get(r["id"])
            if r["row"] == "param" and r["id"] == "bevel" and type_ == "mesh":
                line = fit_note(getattr(self, "_fits", {}), self._sel)
                r["note"] = {"text": line, "kind": "warning"} if line else None
            if r["row"] == "param" and r["id"] in self.FINAL_ONLY.get(type_, ()):
                r["tag"], r["tagHelp"] = "Final", FINAL_TIP
            elif r["row"] == "param" and r["id"] in self.QUICK_APPROX.get(type_, ()):
                r["tag"], r["tagHelp"] = "Final", APPROX_TIP
            p = F.param(type_, r["id"]) if r["row"] == "param" else None
            if p is not None and p.type == "text" and p.kind:
                doc_items = doc_items or list(self.doc.items())
                named = [{"value": i["id"], "label": outline.label_of(i)} for i in doc_items if i["id"] != self._sel
                         and (i.get("type") == p.kind or (p.kind == "item" and i.get("type") in F.ITEMS))]
                r["type"], r["options"] = "choice", ([{"value": "", "label": "None"}] if p.kind in NONE_FIRST else []) + named
        return rows
