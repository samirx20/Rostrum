"""The drum grid's step tool and row menu (a slot mix-in for SoundBridge; SPEC § 3.8, rules in drum_steps.py and
drum_menu.py): the Draw tool's strokes along a row (`stepPress`, `stepTo`, `stepEnd`: one gesture, one undo step) and a
drum row's name (`drumRowClicked`: hear it and select its hits; `drumRowMenu`: Hear, Select all, Fill ▸, Clear, Change
drum ▸). Every row of the menu is an operation (`hit.fill`, `hit.remove`, `hit.set`); Fill row… opens the kit's amounts
popover on the action `fill_row` (amount_actions.py), which is valid only while a row's menu asked for it (`_fill`).
"""
from __future__ import annotations

from PySide6.QtCore import Property, Signal, Slot
from rostrum_gui.edits import Drag

from . import drum_menu, drum_steps as D, inspect, pick, timing
from .drum_rows import kit_drums


class DrumStepSlots:
    fillChanged = Signal()

    # ---- the Draw tool's stroke along a row ---------------------------------------------------------------------
    @Slot(float, float, float, float, int, result=bool)
    def stepPress(self, t, row, px, tol, mods):
        """The Draw tool pressed on a drum row at `t` (`tol`: how near a hit counts as under the pointer; `mods`: 1 Shift =
        an accent, 2 Alt = soft). Starts the stroke (one gesture) and does its first step. False: not on a drum row."""
        roll, i = self._view["roll"], int(round(row))
        drums = roll.get("drums") or []
        if roll.get("kind") != "drums" or not self._track or not 0 <= i < len(drums):
            return False
        drum, grid, root = drums[i], self._grid_now, self.doc.data
        under = pick.roll_at(roll, t, row, tol)
        erase = bool(under) and self.doc.has(under) and self.doc.item(under)["type"] == "hit"
        stroke = D.Stroke(drum, erase, D.LEVELS.get(int(mods) & 3), D.cell_of(t, root, grid, px))
        self.endDrag()

        def go():
            self._drag = Drag(self.doc, self.who, f"{'Erase' if erase else 'Draw'} {inspect.drum_words(drum).lower()} hits")
            self._grab = {"steps": stroke}
            self._drum_step(stroke, [stroke.last], [under] if erase else [])
        if not self._guard(go):
            self.cancelDrag()
            return False
        return True

    @Slot(float, float)
    def stepTo(self, t, px):
        """The pointer moved on with the stroke pressed: every step it passed along the row."""
        stroke = (self._grab or {}).get("steps")
        if self._drag is None or stroke is None:
            return
        cells = D.passed(self.doc.data, self._grid_now, stroke.last, t)
        if cells:
            stroke.last = cells[-1]
            self._guard(lambda: self._drum_step(stroke, cells))

    @Slot()
    def stepEnd(self):
        """Released: the stroke is one change. A click that added a hit selects it; a painted run leaves the selection alone
        (making the settings panel for dozens of hits would cost the release more than a frame)."""
        stroke = (self._grab or {}).get("steps")
        self.endDrag()
        made = [i for i in (stroke.made if stroke else []) if self.doc.has(i)]
        made = made if len(made) == 1 else []
        if made:
            self._pick(made, later=True)
            self._settle()

    def _drum_step(self, stroke, cells, first=()):
        before = {h["id"] for h in self.doc.item(self._track).get("hits", [])}
        calls = D.calls_for(self.doc, self._track, stroke, cells, self._grid_now, first)
        if calls:
            self._drag.preview(calls)
            stroke.made += [h["id"] for h in self.doc.item(self._track).get("hits", []) if h["id"] not in before]

    # ---- a drum row's name ----------------------------------------------------------------------------------------
    def _auditioner(self):
        if self.__dict__.get("_keys_heard") is None:
            from .auditioner import Auditioner
            self._keys_heard = Auditioner(self)
            self._keys_heard.failed.connect(self._fail)
        return self._keys_heard

    def _drum_ids(self, drum, where=None):
        """The ids of `drum`'s hits on this track: all, or those starting in `where` ((from, to) seconds)."""
        a, b = where or (0.0, 1e12)
        return D.hits_in(self.doc, self._track, drum, a, b) if self._track and self.doc.has(self._track) else []

    @Slot(str)
    def drumRowClicked(self, drum):
        """A click on a drum's name: hear it, and select every hit of it (Velocity, Humanise and Delete then act on it)."""
        if not self._track or not self.doc.has(self._track):
            return
        self._auditioner().start({"drum": drum}, inspect.drum_words(drum), self._track)
        ids = self._drum_ids(drum)
        if ids:
            self._pick(ids)

    @Slot(str, float, result="QVariantList")
    def drumRowMenu(self, drum, t):
        """The menu of a drum row's name; `t`: where the pointer last was in the roll (Fill's bar when no range)."""
        root, rng = self.doc.data, self._picks.range
        scope = tuple(rng) if rng else drum_menu.bar_scope(root, t)
        track = self.doc.item(self._track)
        has = bool(self._drum_ids(drum, tuple(rng) if rng else None))
        others = [(d, inspect.drum_words(d)) for d in kit_drums(track) if d != drum]
        return drum_menu.entries(root, drum, inspect.drum_words(drum), scope, tuple(rng) if rng else None, has, others)

    def runDrum(self, parts) -> bool:
        """A drum row menu's choice ("at:drum:<what>:<drum>:…", split on ":" after "drum")."""
        what, drum, rest = parts[0], parts[1], parts[2:]
        words = inspect.drum_words(drum)
        if what == "hear":
            self._auditioner().start({"drum": drum}, words, self._track)
        elif what == "select":
            self._pick(self._drum_ids(drum))
        elif what == "fill":
            every, offset, a, b = (float(x) for x in rest)
            self._act([D.fill_call(self.doc, self._track, drum, a, b, every=every, offset=offset)],
                      f"Fill {words.lower()} · {self._words_of(a, b)}")
        elif what == "fillrow":
            a, b = float(rest[0]), float(rest[1])
            step = self._grid_now.beats(self.doc.data, timing.beat(a, self.doc.data))        # one grid step, in beats
            self._fill = {"track": self._track, "drum": drum, "from": a, "to": b, "step": step}
            self.fillChanged.emit()
            self._hub.choose("fill_row")
        elif what in ("clear", "change"):
            to, span = (None, rest) if what == "clear" else (rest[0], rest[1:])
            ids = self._drum_ids(drum, None if span[0] == "all" else (float(span[0]), float(span[1])))
            if not ids:
                self.say(f"No {words.lower()} hits to {what}")
                return True
            calls = [{"op": "hit.remove", "target": ids, "args": {}}] if to is None else                 [{"op": "hit.set", "target": ids, "args": {"drum": to}}]
            label = f"Clear {words.lower()}" if to is None else f"Change {words.lower()} to {inspect.drum_words(to).lower()}"
            self._act(calls, f"{label} · {len(ids)} hit{'s' if len(ids) != 1 else ''}")
        return True

    def _words_of(self, a, b) -> str:
        from .amount_actions import range_words
        from .action_calls import Facts
        return range_words(Facts(self.doc, [], rng=(a, b)))

    # ---- Fill row… (the amounts popover) -------------------------------------------------------------------------
    @Property(str, notify=fillChanged)
    def fillDrum(self):
        """The drum whose Fill row… is asked for ("" when none): its name is where the popover opens."""
        return (self.__dict__.get("_fill") or {}).get("drum", "")

    def _fill_over(self):
        """The amounts popover closed: the row's Fill row… is not offered any more."""
        if self.__dict__.get("_fill") and not self._hub.amounts.live:
            self._fill = None
            self.fillChanged.emit()
            self._hub.refresh()
