"""Rostrum2D's hooks into the kit's DocBridge: the 2D animation model (route.py, exprs.py). A mix-in for Bridge2D."""
from __future__ import annotations

from rostrum2d import fields as F, fill_fields, stepped, text_anchor
from rostrum2d.frame import TYPE as FRAME
from rostrum_gui import sections
from rostrum_core.keys.layers import stack_of

from . import beat_words, corner_rows, exprs, outline, fill_rows, font_rows, pair_keys, pin_depth, project_picks, route, size_rows, soundtrack_rows, swap_rows

SIBLING_PICKS = {"matte": lambda s: s.get("type") != FRAME,       # any layer beside it that draws a picture can be its
                                                                    # track matte: the frame (the camera) draws none
                 "pathLayer": lambda s: s.get("type") == "path",   # text follows a path layer beside it
                 "ridePath": lambda s: s.get("type") == "path" and not s.get("ridePath"),   # a layer rides one (not a riding one)
                 "parent": lambda s: s.get("type") == "bone"}       # a bone hangs from another bone of its rig, shown by name
RIG_BONE_PICKS = {"bone": ("ik", "bind"), "bone2": ("bind",)}     # an IK chain's lower bone, a bind's bones: the rig's bones by name


# A group's and a rig's box is their children's space, not a size to set; a text's words are typed on the canvas only.
ON_PAGE = {"group": {"w", "h"}, "rig": {"w", "h"}, "text": {"body"}}
for _t in ("drawing", "shape", "text", "image", "video", "path"):      # the frame-by-frame block under the settings has it
    ON_PAGE[_t] = ON_PAGE.get(_t, set()) | {"newHold"}
for _t in F.LAYERS:                      # Locked and Hidden: the lock and eye on the layer's timeline row (and its right-click)
    ON_PAGE[_t] = ON_PAGE.get(_t, set()) | {"locked", "hidden"}
# The frame's panel is Position, Zoom, Rotation and Ride a path (2d-camera SPEC 3.3): its home is never shown (Position's
# reset puts the frame back there); "Animate on" stays the scene's (agents can still set it on the frame).
ON_PAGE[FRAME] |= {"homeX", "homeY", "timing"}


# A text's folded groups would echo its essential rows (Font) as "+ Font", or say nothing ("+ Type"): they read as what they
# hold. (Its Fill group is the Colour row's picker: gradient and opacity live there, so no name is offered for it.)
# Only the words on screen change; the groups' keys stay "Font" / "Type" (kit sections.WORDS).
sections.WORDS.update({("text", "Font"): "Width and slant", ("text", "Type"): "Ligatures and numbers", (FRAME, "Ride"): "Ride a path"})


def _home_reset(rows: list[dict], item: dict | None) -> list[dict]:
    """The frame's Position resets to home (its homeX, homeY), not to the field's fixed default."""
    if not item or item.get("type") != FRAME:
        return rows
    home = {"x": item.get("homeX"), "y": item.get("homeY")}
    return [{**r, "default": home[r["id"]]} if r.get("row") == "param" and r.get("id") in home else r for r in rows]


def _open_line(item: dict) -> set:
    """An open path with its outline on is only its line: the Outline switch could only hide it, so it is not shown."""
    return {"stroke"} if item.get("type") == "path" and "z" not in str(item.get("d", "")).lower() and item.get("stroke") else set()


class Hooks2D:
    def label_of(self, item):
        owner = self.doc.item(self.doc.parent_of(item["id"])[0]) if item.get("type") == "key" else None
        return outline.label_of(item, owner, owner and (lambda t: beat_words.say(self, t + self.offset(owner["id"]))))

    def kind_label(self, item):          # the panel's subtitle and Ctrl+K hints: "Scene", never the raw "Comp"
        return F.LABELS.get(item.get("type", ""), super().kind_label(item))

    def subtitle(self, item):            # the frame is named "Frame": its line says what it is and the export's size
        if item.get("type") == "path":   # a path is named "Path": its line says which kind (so the name doesn't hide it)
            return "Open path" if "z" not in str(item.get("d", "")).lower() else "Closed path"
        if item.get("type") != FRAME:
            return super().subtitle(item)
        comp, d = self.comp(), F.defaults("comp")
        return f"What the export shows · {round(comp.get('width', d['width']))} × {round(comp.get('height', d['height']))}"

    def selection_label(self, ids):      # several selected: "2 layers" (any other mix: the kit's "N items")
        if len(ids) > 1 and all(self.doc.item(i)["type"] in F.ROWS for i in ids):
            return f"{len(ids)} layers"
        return super().selection_label(ids)

    def on_page(self, item):             # fields the screen shows elsewhere (agents still set them through the operation)
        painted = fill_rows.HIDDEN if item.get("type") in fill_fields.OWNERS else set()   # the Fill row's picker has them
        return ON_PAGE.get(item.get("type"), set()) | painted | _open_line(item) | super().on_page(item)

    def starts(self, item):              # a text's anchor at its alignment's point isn't a change (a group opens only for one)
        return text_anchor.starts(item) if item.get("type") == "text" else {}

    def relative_call(self, item_id, param, by, factor):   # +20 / *2: value.set {by} from this layer's own value now
        item = self.doc.item(item_id)
        cur = self.shown_values(item).get(param) if route.drives(item, param) and not exprs.drives(item, param) else None
        if isinstance(cur, bool) or not isinstance(cur, (int, float)):
            return None
        add = by if factor == 1 else cur * (factor - 1)
        add = round(add) if F.param(item["type"], param).integer else round(add, 6)
        return {"op": "value.set", "target": [item_id], "args": {"prop": param, "at": self.own_t(item_id), "by": add}}

    def edit_call(self, item_id, param, value):
        if param == size_rows.ROW and self.doc.item(item_id)["type"] == "comp":      # Scene settings › Format: comp.size
            return size_rows.call(item_id, value)
        if param == fill_rows.ROW:                       # the Fill row's paint: layer.fill (fill_rows.py)
            return fill_rows.call(item_id, value, self.own_t(item_id))
        if param == "fillType":                          # the Fill type choice: layer.fill, which also gives a gradient its stops
            return {"op": "layer.fill", "target": [item_id], "args": {"type": value}}
        if param == "ridePath":                          # Rides path: the agents' layer.ride (X, Y become the offset: 0)
            it = self.doc.item(item_id)
            return {"op": "layer.ride", "target": [item_id], "args": {"path": value, "at": it.get("rideAt", "end"),
                    "along": it.get("rideAlong", 0.0), "turn": it.get("rideTurn", False)}}
        pinned = pin_depth.edit_call(self.doc, item_id, param, value, self._t)
        if pinned is not None and not isinstance(value, str):     # Sticks to the shot, Depth: kept where it shows now
            return pinned
        if isinstance(value, str) and value.lstrip().startswith("="):    # typed "=pulse()" into a field: the expr.set agents call
            return exprs.typed_call(item_id, param, value)
        return route.edit_call(self.doc, item_id, param, swap_rows.edit_value(self.doc.item(item_id), param, value), self.own_t(item_id))

    def _rows(self):          # a swap set's "Shows" is a choice among its children (swap_rows.py); the scene's
        item = self.doc.item(self._sel) if self._sel else None     # Soundtrack among the project's Sound items
        rows = fill_rows.rows(font_rows.rows(size_rows.rows(soundtrack_rows.rows(swap_rows.rows(super()._rows(), item, self._t), item, self.doc.folder), item),
                                             item),
                              item and self.placed_item(item["id"]), self._t, self.comp()["fps"], self._kit.search, self.doc.data)   # placed: keys on a marker read
        rows = _home_reset(project_picks.with_file_names(corner_rows.rows(rows, item), item, self.doc.folder), item)
        return stepped.option_words(rows, not item or self.doc.item(self.doc.parent_of(item["id"])[0]).get("type") == "group")   # File: "pic.png", not the store's copy

    def rows_context(self):               # rows read at the playhead, timed by the markers, in the scene shown
        return self._t, self.marks.times if self.marks else None, self.comp_id

    def shown_values(self, item):
        return route.shown_values(self.placed_item(item["id"]), self._t,     # keys on a marker read as seconds
                                  stack_of(self.doc.data))                 # the animation layers laid over (layerbake.py)

    def anim_state(self, item, param):
        if param == fill_rows.ROW:                       # the Fill row's mark: its colour's or its stops' keys
            return fill_rows.anim_state(item, self.own_t(item["id"]), self.comp()["fps"])
        placed = self.placed_item(item["id"])          # a pair's still half reads as its animated partner (pair_keys.py)
        return route.anim_state(placed, pair_keys.rides(placed, param) or param, self._t, self.comp()["fps"])

    def animate_calls(self, item_id, param, stop=False):
        fps = self.comp()["fps"]
        if param == fill_rows.ROW:
            return fill_rows.animate_calls(self.doc.item(item_id), self.own_t(item_id), fps, stop)
        if not stop and pair_keys.rides(self.placed_item(item_id), param):    # its partner's mark keys only the partner
            return [], f"Key {F.param(self.doc.item(item_id)['type'], param).label} at {self._t:.2f} s"
        calls, label = route.animate_calls(self.placed_item(item_id), param, self._t, fps, stop)      # built in composition seconds
        off = self.offset(item_id)
        for c in calls:                                  # the document writes the layer's own seconds
            for k in ("at", "t"):
                if k in c["args"]:
                    c["args"][k] -= off
        return calls, label
    def list_choices(self, item, param):   # the picks (control "pick"): a shared marker by name, or a sibling layer
        if param in ("marker", "endMarker"):
            return [{"value": m["name"], "label": m["name"]} for m in (self.marks.rows() if self.marks else [])]
        found = project_picks.choices(item, param, self.doc.folder)     # fonts, the project's Sound and 3D items
        if found is not None:
            return found
        if param == "textStyle":                     # the document's text styles (rostrum2d/text_styles.py)
            return [{"value": s["id"], "label": s["name"]} for s in self.doc.data.get("textStyles", [])]
        if param in RIG_BONE_PICKS and item.get("type") in RIG_BONE_PICKS[param]:   # an IK chain's / bind's bone: by name
            rig = self.doc.item(self.doc.parent_of(item["id"])[0])
            return ([{"value": "", "label": "None (rigid)"}] if param == "bone2" else []) + [
                {"value": s["id"], "label": outline.label_of(s, None)} for s in rig.get("bones", [])]
        if param not in SIBLING_PICKS:
            return []
        parent, key, _ = self.doc.parent_of(item["id"])
        # the siblings' list is the same for every one of them (less the item itself): made once per document state, not per
        # item (48 layers picked: 48 x 48 labels, ~60 ms)
        made = self.__dict__.setdefault("_sibling_picks", {})
        if made.get("data") is not self.doc.data:
            made.clear(); made["data"] = self.doc.data
        every = made.get((parent, key, param))
        if every is None:
            every = made[(parent, key, param)] = [{"value": s["id"], "label": outline.label_of(s, None)}
                                                  for s in self.doc.item(parent).get(key, []) if SIBLING_PICKS[param](s)]
        # nearest first, the layers above it before those under it (the one just above is a track matte's usual pick):
        # in the document's order the layer just above came last, out of the list's view (critic 2d-final row 9)
        place = made.get((parent, key, "place"))
        if place is None:
            place = made[(parent, key, "place")] = {s["id"]: i for i, s in enumerate(self.doc.item(parent).get(key, []))}
        mine = place.get(item["id"], -1)
        if param == "parent":                        # never under itself: a bone below it in the chain is left out
            up = {s["id"]: s.get("parent", "") for s in self.doc.item(parent).get(key, [])}
            def under(b, seen=()):
                return b == item["id"] or (b in up and b not in seen and under(up[b], (*seen, b)))
            every = [c for c in every if not under(c["value"])]
        return sorted((c for c in every if c["value"] != item["id"]),
                      key=lambda c: (place[c["value"]] < mine, abs(place[c["value"]] - mine)))

    def expr_state(self, item, param):
        return exprs.state(item, param)

    def clear_expr_calls(self, item_id, param):
        return exprs.clear_calls(self.doc.item(item_id), param)
