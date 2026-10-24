"""A new selection's rows in the settings panel's model (model.py `update(rows, instant=True)`), keeping delegates by id.

Making a settings row costs ~1.5 ms (its label, field, key mark, menus), and giving a row another setting costs more
(its label, help, range, default: ~2-7 ms of bindings), so a pick should make and relabel nothing. Each new row takes the
delegate that last showed the same setting (same id and control), shown or parked, and only its value and validity
change (X stays X from a shape to a text); a setting never shown yet gets a new delegate. Delegates are moved into place
(moves only go up the list, so every position above is final); the ones left over are parked after the shown rows,
absent (valid false: no height, nothing drawn) with their controls, so going back to a kind finds its rows waiting.
The pool is every setting the panel has shown, at most PARKED waiting; the ones parked longest go first.
(Matching a free delegate of the same control instead, relabelled, measured slower than this: ~31-46 vs ~21-27 ms a
pick on the sample, the screen thread's CPU time.)
"""
from __future__ import annotations

from PySide6.QtCore import QModelIndex

PARKED = 150


def _choose(slots: list[dict], rows: list[dict], look) -> list[int | None]:
    """For each new row, the slot (index into slots) that showed the same setting, or None (a new delegate)."""
    by_id = {(s.get("id"), look(s)): i for i, s in enumerate(slots)}
    return [by_id.get((r.get("id"), look(r))) for r in rows]


def repick(m, rows: list[dict]):
    """Show `rows` (the new selection's, all valid) in m's delegates as the module note says."""
    slots = m._shown + m._parked                         # each delegate's data, by slot
    order = list(range(len(slots)))                      # the slot at each model position
    root = QModelIndex()

    def lay(upto):                                       # m's lists as `order` says (positions below `upto` shown)
        m._shown, m._parked = [slots[i] for i in order[:upto]], [slots[i] for i in order[upto:]]

    for k, (r, src) in enumerate(zip(rows, _choose(slots, rows, m._look))):
        if src is None:                                  # made: nothing free is made of this control
            m.beginInsertRows(root, k, k)
            slots.append(r)
            order.insert(k, len(slots) - 1)
            lay(k + 1)
            m.endInsertRows()
            continue
        j = order.index(src)                             # j >= k: the positions above k are final
        if j != k:
            m.beginMoveRows(root, j, j, root, k)
            order.insert(k, order.pop(j))
            lay(k)
            m.endMoveRows()
        lay(k + 1)
        m._send([r], k)
        slots[order[k]] = m._shown[k]
    n = len(rows)
    lay(n)
    for i, s in enumerate(m._parked, n):                 # what showed before and now waits: absent
        if s.get("valid", True):
            m._parked[i - n] = slots[order[i]] = {**s, "valid": False}
            m.dataChanged.emit(m.index(i), m.index(i), [m._ids["valid"]])
    extra = len(m._parked) - PARKED
    if extra > 0:                                        # the end of the list waited longest (moves take from above)
        m.beginRemoveRows(root, m.rowCount() - extra, m.rowCount() - 1)
        del m._parked[-extra:]
        m.endRemoveRows()
