"""Only in this shot and collections for Bridge3D (a slot mix-in, PR1; rostrum3d/shot_layer.py, collection_kit.py).

The switch over the settings ("Changes: All shots | Only <shot>", there only with 2+ shots and something a shot can
change selected) is screen state. While it says Only, every settings edit and every gizmo drag goes to the shown shot
as `<type>.set_in_shot` (the edit hook below), and only the settings a shot can hold are listed. Whatever the switch
says, the panel shows values as the shown shot sees them; a setting the shot holds its own value for carries a "This
shot" tag and a "Use all shots" button (`shot.clear_override`). Collections: the scene list's chip row (CollectionRow.qml).
"""
from __future__ import annotations

from PySide6.QtCore import Property, Slot
from rostrum3d import collection_kit as K, shot_layer as L

from rostrum_core.keys.layers import stack_of
from . import outline, route
from .bridge_signals import Signals3D

CLEAR = "shotonly:clear:"               # a row button's action id: Use all shots for that setting


class ShotOnlyMixin:
    _only = False

    # ---- what the panel reads -----------------------------------------------------------------------------------
    def _shot(self) -> dict:
        return next((s for s in self.doc.data.get("shots", []) if s["id"] == self.shot_id), {})

    def _own(self, item_id: str) -> dict:
        return L.of(self._shot()).get(item_id) or {}

    def _can_only(self) -> bool:
        sel = [i for i in getattr(self._kit, "selection", ()) or () if self.doc.has(i)]
        return (len(self.doc.data.get("shots", [])) > 1 and bool(sel)
                and all(self.doc.item(i).get("type") in L.TYPES for i in sel))

    @Property(bool, notify=Signals3D.outlineChanged)
    def shotOnlyShown(self):
        return self._can_only()

    @Property(bool, notify=Signals3D.outlineChanged)
    def shotOnly(self):
        return self._only and self._can_only()

    @Property(str, notify=Signals3D.outlineChanged)
    def shotOnlyName(self):
        return outline.label_of(self._shot()) if self._shot() else ""

    @Slot(bool)
    def setShotOnly(self, on):
        if bool(on) != self._only:
            self._only = bool(on)
            self.model.update(self._rows())
            self.outlineChanged.emit()

    def _before_followers(self, event):
        """The kit's rows follow a change that reached the selection; a shot's own value is written on the shot, so a
        change that reached the shown shot (with something selected) brings the rows up to date too (the frame after)."""
        super()._before_followers(event)
        sel = self._kit.selection
        if sel and self.doc.has(self.shot_id) and self.reached([self.shot_id]) and not self.reached(sel):
            self._kit.paced.ask() if event.kind == "preview" else self._rows_due().ask()

    def rows_context(self):
        return (*super().rows_context(), self._only, repr(L.of(self._shot())))

    # ---- the kit's hooks ----------------------------------------------------------------------------------------
    def edit_call(self, item_id, param, value):
        it = self.doc.item(item_id)
        if self._only and self._can_only() and L.overridable(it["type"], param):
            return {"op": f"{it['type']}.set_in_shot", "target": [item_id], "args": {"shot": self.shot_id, param: value}}
        return route.edit_call(self.doc, item_id, param, value, self.time)

    def shown_values(self, item):
        return route.shown_values(L.shown(self.doc.data, self.shot_id, item), self.time, stack_of(self.doc.data))

    def anim_state(self, item, param):
        if (self._only and self._can_only()) or param in self._own(item.get("id")):
            return ""                                  # a shot's own value holds (no keys): no key mark
        return route.anim_state(item, param, self.time, self._info["fps"])

    def _rows(self):
        rows = super()._rows()
        if not self._sel or not self.doc.has(self._sel):
            return rows
        type_ = self.doc.item(self._sel)["type"]
        if self._only and self._can_only():
            rows = [r for r in rows if r.get("row") != "param" or L.overridable(type_, r["id"])]
        return self.mark_shot_own(self._sel, rows)

    def mark_shot_own(self, item_id, rows):
        """Rows of `item_id` (an item, or the material rows: materials.py) whose value is the shown shot's own: no key
        mark, and the way back (Use all shots, or a switch's "This shot" tag)."""
        own, shot = self._own(item_id), self.shotOnlyName
        for r in rows:
            if r.get("row") == "param" and r["id"] in own:
                r["anim"] = ""
                if r.get("type") == "toggle":           # (a switch row has no room for a button: the kit's)
                    r["tag"], r["tagHelp"] = "This shot", f"Only {shot} has this; switch it back and it matches every shot again"
                else:                                   # the button is the mark: this value is the shown shot's own
                    r["button"] = {"label": "Use all shots", "id": CLEAR + r["id"], "menu": []}
        return rows

    def shot_only_action(self, action_id: str) -> bool:
        """A row's Use all shots button: the setting goes back to the all-shots value in the shown shot (one step)."""
        if not action_id.startswith(CLEAR) or not self._sel:
            return False
        field = action_id[len(CLEAR):]
        sel = [i for i in self._kit.selection if self.doc.has(i)]
        mats = [m for i in sel if (m := self.shown_values(self.doc.item(i)).get("material")) and self.doc.has(m)]
        calls = [{"op": "shot.clear_override", "target": [self.shot_id], "args": {"item": i, "fields": [field]}}
                 for i in dict.fromkeys(sel + mats) if field in self._own(i)]
        if calls:
            self._guard(lambda: self._done(self.doc.apply(calls, self.who, label="Use all-shots value"), ""))
        return True

    # ---- collections (the scene list's chip row) ------------------------------------------------------------------
    @Property("QVariantList", notify=Signals3D.outlineChanged)
    def collections(self):
        out = []
        for c in K.all_of(self.doc.data):
            ids = K.members(self.doc.data, c)
            shown = [self.doc.item(i).get("visible", True) for i in ids]
            here = [L.shown(self.doc.data, self.shot_id, self.doc.item(i)).get("visible", True) for i in ids]
            out.append({"id": c["id"], "label": K.label(c), "count": len(ids), "ids": ids,
                        "wearers": sum(self.doc.item(i).get("type") in K.USERS for i in ids),
                        "canHide": any(shown), "canShow": not all(shown),           # in every shot
                        "canHideShot": any(here), "canShowShot": not all(here)})   # as the shown shot has them
        return out

    @Slot()
    def newCollection(self):
        """A collection of what is selected (collection.add, one step)."""
        sel = [i for i in self._kit.selection if self.doc.has(i)]
        if not sel:
            return self.fail_line("Error: new collection: select the items to put in it first.")
        call = {"op": "collection.add", "args": {"items": sel}}
        self._guard(lambda: self._done(self.doc.apply([call], self.who, label="New collection"), ""))

    @Slot(str)
    def selectCollection(self, coll_id):
        """Pick a collection's members (screen state): its chip's click. While a light's "Pick what it lights" is on,
        the click adds the collection to what it lights instead (a second click takes it out: place_light.py)."""
        place = getattr(getattr(self, "viewport", None), "place", None)
        if place is not None and place.wants_click():
            return place.toggle(coll_id)
        ids = K.members(self.doc.data, self.doc.item(coll_id)) if self.doc.has(coll_id) else []
        if ids:
            self.selectMany(ids)

    @Slot(str, str)
    def collectionDo(self, coll_id, what):
        """A collection chip's menu: show / hide (all shots), hide or show in this shot only, add the selection, delete."""
        sel = [i for i in self._kit.selection if self.doc.has(i)]
        calls = {"show": ("collection.show", {"visible": True}), "hide": ("collection.show", {"visible": False}),
                 "hideShot": ("collection.show", {"visible": False, "shot": self.shot_id}),
                 "showShot": ("collection.show", {"visible": True, "shot": self.shot_id}),
                 "add": ("collection.set", {"include": sel}), "delete": ("collection.remove", {})}
        if what not in calls:
            return self.fail_line(f"Error: collection: {what!r} is not something a collection does.")
        op, args = calls[what]
        call = {"op": op, "target": [coll_id], "args": args}
        self._guard(lambda: self._done(self.doc.apply([call], self.who, label=op), ""))

    @Slot(str, str)
    def collectionMaterial(self, coll_id, material_id):
        """A chip's Give material…: every member that can wear one takes it (collection.material, one step)."""
        call = {"op": "collection.material", "target": [coll_id], "args": {"material": material_id}}
        self._guard(lambda: self._done(self.doc.apply([call], self.who, label="Give material"), ""))

    @Slot(str, str)
    def renameCollection(self, coll_id, name):
        if name.strip():
            call = {"op": "collection.set", "target": [coll_id], "args": {"name": name.strip()}}
            self._guard(lambda: self._done(self.doc.apply([call], self.who, label="Rename collection"), ""))
