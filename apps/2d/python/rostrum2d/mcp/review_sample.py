"""The film sampled once for review's frame and cover checks (review_frame, review_cover): every layer at each sample time
(geometry.flatten) and, only when a check asks, each character's posed parts (the engine poses them: placement.asker).
Also the small rules those checks share: what counts as seen, what is a backdrop, how much of the frame boxes cover."""
from __future__ import annotations

from functools import cached_property

import numpy as np

from rostrum2d.frame import view

from . import edge_cut
from .geometry import _apply, _invert, comp_size, drawn_box, flatten

SEEN = 0.1            # opacity from which a layer counts as showing (a nearly clear layer is ignored)
BACKDROP = 0.8        # a layer covering this share of the frame or more is the background (or a full-frame wash over it)
GRID = (64, 36)       # cells the frame is cut into to measure covered area


class Sampled:
    """One composition at `times`: `frames` [(t, nodes)], `parts` per time {rig id: [part quads in picture px]}."""

    def __init__(self, doc_data: dict, comp: dict, times: list[float], step: float):
        self.doc_data, self.comp, self.times, self.step = doc_data, comp, times, step
        self.W, self.H = comp_size(comp)
        self.duration = float(comp.get("duration", 5.0))
        self.notes: list[str] = []

    @cached_property
    def frames(self) -> list[tuple[float, list[dict]]]:
        return [(t, flatten(self.comp, t)) for t in self.times]

    @cached_property
    def parts(self) -> list[dict[str, list[list[tuple]]]]:
        """Per time {rig id: each drawn part's 4 corners in picture px}; a rig the engine can't pose is left out (a note)."""
        from rostrum2d import placement
        rigs = {k: v for k, v in edge_cut.rig_parts(self.comp).items() if v}
        if not rigs or not self.times:
            return [{} for _ in self.times]
        try:
            ask = placement.asker(self.doc_data, self.comp["id"], (min(self.times), max(self.times)))
        except Exception as e:      # noqa: BLE001  (no engine: the character checks are skipped, said in a note)
            self.notes.append(f"characters not measured for staging: {e}")
            return [{} for _ in self.times]
        out = []
        for t in self.times:
            inv = _invert(view.world_matrix(self.comp, view.shot(self.comp, t), {"screenLock": True}))
            row = {}
            for rid, ids in rigs.items():
                quads = [[_apply(inv, *placement.comp_point(p, x, y)) for x, y in ((0, 0), (p["w"], 0), (p["w"], p["h"]), (0, p["h"]))]
                         for p in edge_cut.ask_drawn(ask, t, ids).values() if inv and p.get("w") and p.get("h")]
                if quads:
                    row[rid] = quads
            out.append(row)
        return out

    def seen(self, n: dict) -> bool:
        """Showing in the picture now: in its time, not nearly clear, not only a matte, painting something on screen. A rig's own
        box is not its body: a character is measured by its posed `parts`."""
        if not n["in_time"] or n["opacity"] < SEEN or n["matte_for"] or n["type"] == "rig" or n["type"] == "group" and not n["paint"]:
            return False
        x0, y0, x1, y1 = drawn_box(n)
        return x1 > 0 and y1 > 0 and x0 < self.W and y0 < self.H and (x1 - x0) * (y1 - y0) > 4

    def share(self, box) -> float:
        """The share of the frame a box (x0, y0, x1, y1) covers inside it."""
        x0, y0, x1, y1 = box
        return max(0.0, min(x1, self.W) - max(x0, 0)) * max(0.0, min(y1, self.H) - max(y0, 0)) / (self.W * self.H)

    def backdrop(self, n: dict) -> bool:
        return self.share(drawn_box(n)) >= BACKDROP

    def cells(self, boxes: list[tuple]) -> np.ndarray:
        """The GRID cells the union of `boxes` (x0, y0, x1, y1) covers."""
        gw, gh = GRID
        cells = np.zeros((gh, gw), bool)
        for x0, y0, x1, y1 in boxes:
            a, b = max(0, int(x0 / self.W * gw + 0.5)), min(gw, int(x1 / self.W * gw + 0.5))
            c, d = max(0, int(y0 / self.H * gh + 0.5)), min(gh, int(y1 / self.H * gh + 0.5))
            if a < b and c < d:
                cells[c:d, a:b] = True
        return cells

    def background(self, nodes: list[dict]) -> str:
        """The picture's ground: the top backdrop layer's fill (or its id) or the composition's background colour."""
        for n in reversed(nodes):
            if self.seen(n) and n["type"] != "text" and self.backdrop(n):
                return str(n["props"].get("fill") or n["id"])
        return str(self.comp.get("background", "#000000"))


def quad_points(quad: list[tuple]) -> list[tuple[float, float]]:
    """Nine points spread over a part's quad (its middle, and a 3 x 3 grid at a quarter in from its corners)."""
    (ax, ay), (bx, by), _, (dx, dy) = quad
    return [(ax + (bx - ax) * u + (dx - ax) * v, ay + (by - ay) * u + (dy - ay) * v) for u in (0.2, 0.5, 0.8) for v in (0.2, 0.5, 0.8)]


def runs(flags: list[bool], times: list[float], step: float, least: float) -> list[tuple[float, float, int, int]]:
    """(start, end, first index, last index) of each run of true flags lasting at least `least` seconds."""
    out, a = [], None
    for i, on in enumerate(list(flags) + [False]):
        if on and a is None:
            a = i
        elif not on and a is not None:
            t0, t1 = times[a], times[i - 1] + step
            if t1 - t0 >= least - 1e-9:
                out.append((round(t0, 2), round(t1, 2), a, i - 1))
            a = None
    return out
