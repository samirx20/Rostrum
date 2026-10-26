"""The bridge's edit slots (a slot mix-in, see parts.py): every one an operation through doc.apply, recorded with
the person's name. A scrub goes through doc.gesture (one change for the whole drag). A refused edit fails loudly:
`_guard` reports it (console + status), never swallows it, never crashes. With several items selected, each edit is
ONE change on every one of them (one doc.apply with a call per item; one scrub moves them all).
The mix-in reaches the bridge through `self` (`self.doc`, `self.who`, `self._kit` (its state), `self._fail`,
`self._set_status`, `self._commands`, `self.select`) and the app's hooks (`edit_call`, `animate_calls`, ...).
"""
from __future__ import annotations

from PySide6.QtCore import Slot
from rostrum_core import RostrumError, desk

from . import commands, pairs
from .edits import Scrub, edit_label, field_param
from .parts import SlotMixin


class EditSlots(SlotMixin):
    @Slot(str, "QVariant", result=bool)
    def setValue(self, param, value):
        """One inspector edit = one change on the items it is for (quick repeats of the same field merge: the core's
        nudge). A typed value goes to the items held when its typing started (holdEdit), whatever is selected now."""
        ids = self._targets(param)
        if not ids:
            self._fail(f"Error: setValue {param}: the item(s) it was typed for are gone; {value!r} dropped.",
                       "The typed value was dropped: the item it was typed for is gone.")
            return False
        return self._guard(lambda: self._apply([self.edit_call(i, param, value) for i in ids],
                                               self._many(self._edit_label(ids[0], param, value), len(ids))))

    @Slot(str, float, float, result=bool)
    def setRelative(self, param, by, factor):
        """A typed +20 / *2 / /2: each item's own value, as `value.set {by}` (the call an agent makes; `relative_call`),
        all of them one change. `by` adds (stored units); `factor` scales (1 = not a scaling)."""
        ids = self._targets(param)
        calls = [c for c in (self.relative_call(i, param, by, factor) for i in ids) if c]
        if not calls:
            self._fail(f"Error: setRelative {param}: no item can take it.", "This setting can't take +20 or *2 here; type the number.")
            return False
        return self._guard(lambda: self._apply(calls, self._many(edit_label(self.doc, ids[0], param, by), len(calls))))

    def relative_call(self, item_id, param, by, factor):
        """The `value.set {by}` call for one item, or None (an app that takes +20 / *2 overrides this)."""
        return None

    @Slot(str)
    def holdEdit(self, param):
        """A settings field's caret went in: what it commits goes to the items selected now (pending.py)."""
        self.hold_ids(param, self._kit.selection)

    @Slot(str)
    def releaseEdit(self, param):
        """The field's caret left (after its commit)."""
        if self._kit.held and self._kit.held[0] == param:
            self._kit.held = None

    def hold_ids(self, param, ids):
        """One rule for every typed field: it belongs to these items from its caret going in (the key panel's too)."""
        self._kit.held = (param, list(ids))

    def held_ids(self, param, current):
        """The items a typed value is for: those held for `param` (still in the document), else `current`."""
        held = self._kit.held
        ids = held[1] if held and held[0] == param else current
        return [i for i in ids if self.doc.has(i)]

    def _targets(self, param):
        return self.held_ids(param, self._kit.selection)

    @Slot(str)
    def toggleAnimate(self, param):
        """A click on a row's key mark: the app's animate_calls (route.py's key mark), as one change. A pair's half (X of
        Position, W of Size: pairs.py) is the whole pair, labelled by the pair. Several items or halves: those without a
        key at the playhead get one; when all have one, those keys go. A deleted key is said in the top bar: a click never
        takes animation away unseen."""
        def go():
            names = pairs.partner_of(self._kit.static, param)
            states = {(i, n): self.anim_state(self.doc.item(i), n) for i in self._kit.selection for n in names}
            todo = [k for k, s in states.items() if s in ("still", "keyed")] or [k for k, s in states.items() if s] or list(states)
            self._animate(param, names, todo, [self.animate_calls(i, n) for i, n in todo])
        self._guard(go)

    @Slot(str)
    def stopAnimating(self, param):
        """The key mark's right-click › Stop animating: every key of the field goes, keeping the value at the playhead."""
        def go():
            names = pairs.partner_of(self._kit.static, param)
            todo = [(i, n) for i in self._kit.selection for n in names if self.anim_state(self.doc.item(i), n) in ("keyed", "onkey")]
            if todo:
                self._animate(param, names, todo, [self.animate_calls(i, n, stop=True) for i, n in todo])
        self._guard(go)

    def _animate(self, param, names, todo, made):
        label = made[0][1]
        if len({n for _, n in todo}) > 1:            # both halves: "Animate Position", never "Animate X"
            op = self._kit.op_kind[0]
            own = next(p.label for p in op.params if p.name == names[0])
            pair = next(r["label"] for r in self._kit.static if r.get("half") == "first" and r["id"] == names[0])
            label = label.replace(own, pair)
        ids = list(dict.fromkeys(i for i, _ in todo))
        calls = [c for calls, _ in made for c in calls]
        change = self.doc.apply(calls, self.who, label=self._many(label, len(ids)))
        gone = any(c["op"] in ("key.remove", "key.clear") for c in calls)
        self._done(change, "", said=gone)            # "Delete Zoom key at 6.00 s" / "Stop animating Zoom" stays in view

    @Slot(str)
    def clearExpression(self, param):
        """The clear button on a row driven by an expression: the app's clear_expr_calls, as one change."""
        self._guard(lambda: self._apply_each(lambda i: self.clear_expr_calls(i, param), self._kit.selection))

    @Slot(str)
    def beginScrub(self, param):
        self.endScrub()
        def go():
            s = Scrub(self.doc, self.who, list(self._kit.selection), param, self.edit_call)
            s._ctx.label = self._many(self._edit_label(s.item_id, param, None), len(s.items))
            self._kit.scrub = s
        self._guard(go)

    def _edit_label(self, item_id, param, value):
        """What the history says for a settings edit (edits.edit_label). A row that is no field of the item's operation
        (an app's own row: an EQ band, Sound's Feel amounts, edited through its edit_call) says its row's words."""
        row = None if field_param(self.doc, item_id, param)[1] is not None else next(
            (r for r in self.model.rows if r.get("row") == "param" and r.get("id") == param), None)
        if row is None:
            return edit_label(self.doc, item_id, param, value)
        if row.get("type") == "toggle":
            return f"Turn {'on' if value else 'off'} {row['label']}"
        if row.get("type") == "choice" and value is not None:
            return f"{row['label']}: " + next((o["label"] for o in row.get("options") or [] if o["value"] == value), str(value))
        return f"Change {row['label']}"

    @Slot(str, "QVariant")
    def scrub(self, param, value):
        if self._kit.scrub is None or self._kit.scrub.name != param:
            self.beginScrub(param)
        if self._kit.scrub is not None:
            self._guard(lambda: self._kit.scrub.preview(value))

    @Slot()
    def endScrub(self):
        self._close_scrub(cancel=False)

    @Slot()
    def cancelScrub(self):
        self._close_scrub(cancel=True)

    @Slot(str, result="QVariantList")
    def commands(self, query):
        return [{k: c[k] for k in ("key", "label", "hint")} for c in commands.search(self._commands(), query)]

    @Slot(str, result=bool)
    def run(self, key):
        """Run a command-bar command by key: its calls as one change (or a selection)."""
        cmd = next((c for c in self._commands() if c["key"] == key), None)
        if cmd is None:
            self._fail(f'Error: command bar: "{key}" is not available right now.')
            return False
        if "select" in cmd:
            self.select(cmd["select"])
            return True
        if "reveal" in cmd:                 # a setting that needs a value: its field in the settings panel (commands.field_rows)
            return self.revealField(cmd["reveal"])
        if "do" in cmd:                     # an app's own command that isn't an operation (extra_commands)
            if not callable(cmd["do"]):     # a word where a function belongs: say so, never "'str' is not callable"
                self._fail(f'Error: command bar: "{key}" has "do" = {cmd["do"]!r}; it must be a function (extra_commands).')
                return False
            return self._guard(cmd["do"])
        return self._guard(lambda: self._apply(cmd["calls"], cmd["label"]))

    @Slot()
    def undo(self):
        """The person's newest change in this document or a joined one (the markers): one history (desk.py). A change
        still open (a colour picker's session, a field being dragged) is closed first, so Ctrl+Z takes back what was
        just done there, never "Nothing to undo"; the control's next change opens a new one (`scrub`)."""
        self._close_scrub(cancel=False)
        self._guard(lambda: self._step(desk.undo, "Nothing to undo"))

    @Slot()
    def redo(self):
        self._close_scrub(cancel=False)
        self._guard(lambda: self._step(desk.redo, "Nothing to redo"))

    def _step(self, fn, nothing):
        pairs = [(self.doc, None)] + [(p.history_doc(), p) for p in self._kit.partners]
        pairs = [(d, p) for d, p in pairs if d is not None]
        hit = fn([d for d, _ in pairs], self.who, self.open_item)
        for doc, _ in hit.all if hit is not None else ():      # a step across documents changed each of them
            partner = next((p for d, p in pairs if d is doc), None)
            if partner is not None:
                partner.stepped(doc)
        self._done(hit[1] if hit else None, nothing, said=True)

    def _apply(self, calls, label):
        self._done(self.doc.apply(calls, self.who, label=label), "")

    def _apply_each(self, calls_of, ids):
        """`calls_of(id) -> (calls, label)` for each item, applied as one change."""
        made = [calls_of(i) for i in ids]
        self._apply([c for calls, _ in made for c in calls], self._many(made[0][1]) if len(made) > 1 else made[0][1])

    def _many(self, label, n=None):
        n = len(self._kit.selection) if n is None else n
        return f"{label} on {n} items" if n > 1 else label

    def _close_scrub(self, cancel):
        s, self._kit.scrub = self._kit.scrub, None
        if s is not None:
            self._guard(lambda: self._done(s.end(cancel), ""))

    def _done(self, change, nothing, said=False):
        """A person's own change clears the message (they see it on screen; its name is on ↶ and in History);
        undo / redo show their change's own label, which the core words once ("Undid: Move title"); no change
        says `nothing`."""
        self._set_status(nothing if change is None else change.label if said else "")

    def _guard(self, fn) -> bool:
        """Run an edit; a refusal is reported (console + status), never swallowed, never a crash."""
        try:
            fn()
            return True
        except RostrumError as e:
            self._fail(e.line(), e.person())
            return False
