"""Lifted strokes' wet pictures kept on screen until the canvas's picture holds them (wet.py).

The wet ink has one tip picture: a stroke lifted before the picture with it landed lost its ink the moment the next
stroke started, so a burst of quick strokes showed only the last one until the paint caught up (2D final critic: 13
dry-brush strokes, 12 gone). Now the lifted stroke's picture moves here when the next one starts, and each stays until
the picture on screen holds its stroke, or the stroke has left the document (an undo). `holds(sid)` answers that.
"""
from __future__ import annotations


def has_stroke(data, sid: str) -> bool:
    """Whether the document tree `data` holds the stroke `sid` (drawings' and paintings' paint; points are skipped)."""
    stack = [data]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if node.get("id") == sid:
                return True
            stack.extend(v for k, v in node.items() if k != "points" and isinstance(v, (dict, list)))
        elif isinstance(node, list):
            stack.extend(v for v in node if isinstance(v, (dict, list)))
    return False


class Kept:
    """[{sid, part, x, y, w, h}] shown by WetInk.qml (image://wet/<part>-1), in the order they were drawn."""

    def __init__(self, provider):
        self.provider, self.rows, self._n = provider, [], 0

    def keep(self, sid: str, image, box: dict) -> None:
        if not sid or image is None or image.isNull() or not box:
            return
        self._n += 1
        part = f"k{self._n}"
        self.provider.put(part, image)
        self.rows = [*self.rows, {"sid": sid, "part": part, **{k: box.get(k, 0) for k in ("x", "y", "w", "h")}}]

    def settle(self, holds) -> bool:
        """Drops the pictures whose stroke `holds(sid)` says is shown (or gone). True: some went."""
        left = [r for r in self.rows if not holds(r["sid"])]
        if len(left) == len(self.rows):
            return False
        for r in self.rows:
            if r not in left:
                self.provider.drop(r["part"])
        self.rows = left
        return True
