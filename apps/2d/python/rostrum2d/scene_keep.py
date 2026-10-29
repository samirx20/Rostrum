"""The screen's scene description after a change: what scene.describe gives (equal, ==), made again only for what the
change touched; every other item's node is the previous call's own object (`is`), at every depth. The engine is then
sent only the new nodes (scene_change.py).

What a change touched has one source of truth: documents are copy on write (rostrum_core.edits.fork copies exactly
the items an edit changes and the items above them; every other item stays the same object). So an item is described
again unless it is the very object described last time, in the same context:
  - what it is made with from above: its group's stepped timing and its swap set's shown-or-not per frame;
  - the baked expression and auto-layout keys (exprbake, layoutbake) of it and everything inside it, compared by value
    (an expression may read another layer, the playhead's markers or the beats);
  - the call's: composition, project folder, span, markers, `later` or not, the composition's fps and length, and the
    document's paintings (a painted fill reads its painting): any change of these forgets everything.
Inputs outside the document that the call can't see (a 3D render finishing, a picture or font appearing on disk) make
the caller `forget()` (the screen's bridge2d does on a 3D render, a marker move and made paint pictures). A node whose
making listed paint pictures into `later` is kept with those jobs (`pending`): kept, it lists the same jobs into `later`
again, so the caller still sees what is not made; once the caller has run any of them (`ran`), it is described again
(a look makes only the pictures of the frames it shows, so a painted film always has some left: before, its drawings
were described again on every look, ~1-1.6 s). Its warnings (a placeholder) and missing fonts are said again each
time it is kept. Layers timed from a marker keep their timed copy between calls
(retime.timed's memo), so they are kept too.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import scene


@dataclass(eq=False)
class _Kept:
    item: dict                      # the document item (the timed copy) the node was made from
    key: tuple                      # (stepped timing from above, swap vis)
    node: dict
    ids: frozenset                  # its id and every id inside it: whose baked keys it read
    inside: dict                    # {id: _Kept} of everything inside it, carried over when it is kept
    warnings: list
    fonts: list                     # (text id, missing font) pairs
    pending: list                   # the paint-picture jobs its making put in `later` (not made then)


class Keeper:
    def __init__(self):
        self.forget()

    def forget(self):
        """Describe everything again next time (an input outside the document changed)."""
        self._kept, self._baked, self._context, self._paintings, self._timed, self._comp = {}, {}, None, None, {}, None
        self.reused = self.made = 0                 # the last call's counts (a timing line, tests)

    def describe(self, doc_data: dict, comp_id: str | None = None, markers: dict | None = None, folder=None,
                 span: tuple[float, float] | None = None, later: list | None = None) -> dict:
        """scene.describe's description of the same arguments, reusing what didn't change."""
        context = (comp_id, None if folder is None else str(folder), span, later is None, dict(markers or {}))
        paintings = doc_data.get("paintings") or []      # (the list is new on every change; each painting isn't)
        if context != self._context or len(paintings) != len(self._paintings or ()) or any(
                a is not b for a, b in zip(paintings, self._paintings or ())):
            self.forget()
            self._context, self._paintings = context, list(paintings)
        comp, fps, baked, where = scene.prepare(doc_data, comp_id, markers, folder, span, later, self._timed)
        if (fps, where["until"]) != self._comp:      # every node's keys run to the composition's end
            self._kept, self._baked = {}, {}
        old = self._baked
        self._changed = {k for k in old.keys() | baked.keys() if old.get(k) != baked.get(k)}
        self._now, self._made, self._stack, self.reused, self.made = baked, {}, [], 0, 0
        where["make"] = self._make
        out = scene.finish(scene._node(comp, fps, baked, where), where)
        self._kept, self._baked, self._comp = self._made, baked, (fps, where["until"])
        return out

    def _make(self, item, fps, baked, where, n, vis):
        if baked is not self._now:                  # not a document child (a gradient fill's stops): made as it is
            return scene._node(item, fps, baked, where, n, vis)
        key = (n, vis)
        got = self._kept.get(item["id"])
        if got is not None and got.item is item and got.key == key and self._changed.isdisjoint(got.ids) and (
                not got.pending or where.get("later") is not None):
            if got.pending:                         # its pictures still to make: listed again, as describing it would
                where["later"].extend(got.pending)
            if got.warnings:
                where.setdefault("warnings", []).extend(got.warnings)
            if got.fonts:
                where.setdefault("missing_fonts", {}).update(got.fonts)
            self._keep(got)
            self.reused += 1
            return got.node
        warned, fonts = len(where.get("warnings", ())), len(where.get("missing_fonts", ()))
        later = where.get("later")
        listed = len(later) if later is not None else 0
        self._stack.append({})
        try:
            node = scene._node(item, fps, baked, where, n, vis)
        finally:
            inside = self._stack.pop()
        self.made += 1
        self._keep(_Kept(item, key, node, frozenset(inside) | {item["id"]}, inside,
                         where.get("warnings", [])[warned:], list(where.get("missing_fonts", {}).items())[fonts:],
                         list(later[listed:]) if later is not None else []))
        return node

    def ran(self, jobs: list) -> None:
        """The caller made these pictures (jobs from `later`): every kept node that listed one (and the groups round
        it, which listed it too) is described again next time, with the made picture in place of its stand-in."""
        done = {id(j) for j in jobs}
        self._kept = {k: v for k, v in self._kept.items() if not any(id(j) in done for j in v.pending)}

    def _keep(self, got: _Kept):
        """Remember `got` (and what is inside it) for the next call, and in the node being made around it."""
        self._made.update(got.inside)
        self._made[got.item["id"]] = got
        if self._stack:
            self._stack[-1].update(got.inside)
            self._stack[-1][got.item["id"]] = got
