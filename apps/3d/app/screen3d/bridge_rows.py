"""The settings panel's rows for Bridge3D (a slot mix-in): the kit's rows with the data groups left out, the Final tags,
a field that names another item shown as a choice (and the "Stylized" / "Final · Stylized" tags), and facts_of: the SCREEN's facts added to the kind's (`animating`: a
setting valid only while animating shows only on the Animate page; agents have no pages, so for them it always holds)."""
from __future__ import annotations

from rostrum3d import fields as F

from .actions3d import fit_note
from .materials import USERS

FINAL_TIP = "Shows in Final, not in the Quick view"
APPROX_TIP = "Shows fully in Final; the Quick view only hints at it"
STYLIZED_TIP = "Shows in the Stylized look only"
FINAL_STYLIZED_TIP = "Shows in Final and Stylized, not in the Quick view"
NONE_FIRST = {"material": "None", "item": "None",     # fields naming another item that may name none, and what "" reads
              "collection": "Everything"}             # ("" = no material, focus on a distance, render everything)
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
    STYLIZED_ONLY: dict = {}            # set by Bridge3D: fields only the Stylized look shows
    FINAL_STYLIZED: dict = {}           # set by Bridge3D: fields Final and Stylized show, Quick doesn't

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
        shown at the playhead). Not the playhead itself: what the selection shows at it, so a scrub step works the rows
        out again only when a shown value or a key's place under the playhead changed (a still item: never)."""
        return self._page, self._sculpting(), getattr(self, "shot_id", None), self._at_playhead()

    def _at_playhead(self) -> tuple:
        """The selection's keyed values and key marks at the playhead, and a copies item's seen count."""
        out = []
        for i in getattr(self._kit, "selection", ()) or ():
            if not self.doc.has(i):
                continue
            it = self.doc.item(i)
            props = sorted({k["prop"] for k in it.get("keys", []) if "prop" in k})
            shown = self.shown_values(it) if props else it
            out += [(i, p, shown.get(p), self.anim_state(it, p)) for p in props]
            if it.get("type") == "copies":
                out.append((i, self.copies_note(i)))
        return tuple(out)

    def _patch_playhead(self, was: tuple, now: tuple) -> bool:
        """A scrub step's panel: one item selected and only keyed numbers moved, so only those rows' value and key mark
        are new (working out the whole panel again cost ~5 ms a frame). False: the caller works the rows out."""
        if len(getattr(self._kit, "selection", ())) != 1 or len(was) != len(now):
            return False
        new = {}
        for a, b in zip(was, now):
            if len(b) != 4 or a[:2] != b[:2]:
                return False
            if a != b:
                if not isinstance(b[2], (int, float)) or isinstance(b[2], bool):
                    return False                   # a keyed choice or switch may show or hide other rows
                new[b[1]] = b
        rows = list(self.model.rows)
        for n, r in enumerate(rows):
            if r.get("row") == "param" and r.get("id") in new:
                _, _, value, anim = new.pop(r["id"])
                rows[n] = {**r, "value": value, "anim": anim}
        if new:
            return False
        self.model.update(rows)
        return True

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
            if r["row"] == "param" and r["id"] == "count" and type_ == "copies":
                line = self.copies_note(self._sel)             # "212 of 400 in Hero 01", or "400 copies"
                r["note"] = {"text": line, "kind": "hint"} if line else None
            if r["row"] == "param" and r["id"] in self.FINAL_ONLY.get(type_, ()):
                r["tag"], r["tagHelp"] = "Final", FINAL_TIP
            elif r["row"] == "param" and r["id"] in self.QUICK_APPROX.get(type_, ()):
                r["tag"], r["tagHelp"] = "Final", APPROX_TIP
            elif r["row"] == "param" and r["id"] in self.STYLIZED_ONLY.get(type_, ()):
                r["tag"], r["tagHelp"] = "Stylized", STYLIZED_TIP
            elif r["row"] == "param" and r["id"] in self.FINAL_STYLIZED.get(type_, ()):
                r["tag"], r["tagHelp"] = "Final · Stylized", FINAL_STYLIZED_TIP
            p = F.param(type_, r["id"]) if r["row"] == "param" else None
            if p is not None and p.type == "text" and p.kind:
                doc_items = doc_items or list(self.doc.items())
                named = [{"value": i["id"], "label": outline.label_of(i)} for i in doc_items if i["id"] != self._sel
                         and (i.get("type") == p.kind or (p.kind == "item" and i.get("type") in F.ITEMS))]
                r["type"], r["options"] = "choice", ([{"value": "", "label": NONE_FIRST[p.kind]}] if p.kind in NONE_FIRST else []) + named
        return rows
