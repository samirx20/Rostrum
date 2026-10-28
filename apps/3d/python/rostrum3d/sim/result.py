"""A stored simulation result, read: the core's `bodies.bin` (float32 little-endian, (end - start + 1) × rows × 7:
x y z qx qy qz qw) and `result.json` (the core's reply and the body order) in the cache entry's folder.

Turns: the core gives each row's turn as a quaternion; the items keep rotateXYZ degrees (rx, then ry, then rz: R = Rz·Ry·Rx,
aim.euler / poly.turn_matrix), made continuous frame to frame (rigs.continuous) so nothing spins the long way round between
two frames.

Timing and Simplify (brief 26a) are applied here, when reading, never stored: Simplify n keeps every nth sample from the
result's first frame (and its last) and moves in a straight line between them (turns: the shortest way); Timing On 2s / On 3s
holds each frame's value for 2 or 3 frames, counted from the shot's start, like hand animation.

Cloth (brief 26b) is never read here: the core reads its `cloth_<item>.bin` itself when it builds the stage (the mesh node's
`cloth`, overlay.py), Timing and Simplify included. Its layout (ENGINE_CONTRACT § Simulation), little-endian:
"RCL1", int32 points, triangles, frames, start; int32 × 3 × triangles; float32 × 2 × points (u v); then
float32 × 3 × points per frame (the item's own space).
"""
from __future__ import annotations

import array
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

from .. import aim, rigs

BIN, JSON = "bodies.bin", "result.json"
ROW = 7
CLOTH_HEADER = 20


def cloth_file(item: str) -> str:
    return f"cloth_{item}.bin"


def cloth_bytes(points: int, triangles: int, frames: int) -> int:
    return CLOTH_HEADER + 12 * triangles + 8 * points + 12 * points * frames


@dataclass
class Result:
    start: int
    end: int
    rows: int
    data: array.array                            # float32, frame-major
    bodies: list[dict]                           # [{"item", "copy", "row"}] as the core gave them
    reply: dict
    folder: Path

    def sample(self, frame: int, row: int) -> tuple[list[float], list[float]]:
        """(position, quaternion x y z w) of a row at a frame of the result (outside it: held at its ends)."""
        f = min(max(frame, self.start), self.end) - self.start
        o = (f * self.rows + row) * ROW
        v = self.data[o:o + ROW]
        return list(v[:3]), list(v[3:])

    def rows_of(self, item: str) -> list[int]:
        return sorted(b["row"] for b in self.bodies if b["item"] == item)

    def appear_of(self, item: str) -> list[int]:
        """Per row of `item` (rows_of order): the shot frame each copy of a stream appears and falls (before it, it is
        not there); [] when none waits hidden (no stream)."""
        mine = sorted((b for b in self.bodies if b["item"] == item), key=lambda b: b["row"])
        return [int(b.get("appear", self.start)) for b in mine] if any("appear" in b for b in mine) else []


def read(folder) -> Result:
    folder = Path(folder)
    meta = json.loads((folder / JSON).read_text(encoding="utf-8"))
    (start, end), rows = meta["frames"], meta["rows"]
    data = array.array("f")
    raw = (folder / BIN).read_bytes()
    want = (end - start + 1) * rows * ROW * 4
    if len(raw) != want:
        raise ValueError(f"the stored simulation in {folder} is {len(raw)} bytes, expected {want}; simulate again")
    data.frombytes(raw)
    if sys.byteorder != "little":
        data.byteswap()
    return Result(start, end, rows, data, meta["bodies"], meta, folder)


# --- turns -----------------------------------------------------------------------------------------------------------

def quat_matrix(q) -> list[list[float]]:
    x, y, z, w = q
    n = math.sqrt(x * x + y * y + z * z + w * w) or 1.0
    x, y, z, w = x / n, y / n, z / n, w / n
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]


def euler_quat(rx: float, ry: float, rz: float) -> list[float]:
    """rotateXYZ degrees as a quaternion x y z w (the core's form of an item's turn)."""
    def axis(i, deg):
        h = math.radians(deg) / 2
        q = [0.0, 0.0, 0.0, math.cos(h)]
        q[i] = math.sin(h)
        return q
    return _mul(axis(2, rz), _mul(axis(1, ry), axis(0, rx)))


def _mul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return [aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz]


def quat_euler(q) -> tuple[float, float, float]:
    return aim.euler(quat_matrix(q))


def _slerp(a, b, t: float):
    d = sum(x * y for x, y in zip(a, b))
    if d < 0:
        b, d = [-x for x in b], -d
    if d > 0.9995:
        out = [x + (y - x) * t for x, y in zip(a, b)]
    else:
        th = math.acos(d)
        s0, s1 = math.sin((1 - t) * th) / math.sin(th), math.sin(t * th) / math.sin(th)
        out = [s0 * x + s1 * y for x, y in zip(a, b)]
    n = math.sqrt(sum(x * x for x in out)) or 1.0
    return [x / n for x in out]


# --- reading through Timing and Simplify -------------------------------------------------------------------------------

def stylized(res: Result, row: int, frames, shot_start: int, step: int = 1, simplify: int = 1):
    """[(position, quaternion)] of a row at each of `frames`: Simplify `simplify` (every nth sample, straight between),
    then Timing `step` (each value held `step` frames from `shot_start`)."""
    out = []
    for f in frames:
        f = shot_start + ((f - shot_start) // step) * step if step > 1 else f
        f = min(max(f, res.start), res.end)
        if simplify > 1:
            i = f - res.start
            a = res.start + (i // simplify) * simplify
            b = min(a + simplify, res.end)
            if b == a or f == a:
                out.append(res.sample(a, row))
                continue
            t = (f - a) / (b - a)
            (pa, qa), (pb, qb) = res.sample(a, row), res.sample(b, row)
            out.append(([x + (y - x) * t for x, y in zip(pa, pb)], _slerp(qa, qb, t)))
        else:
            out.append(res.sample(f, row))
    return out


def trs(samples) -> dict[str, list[float]]:
    """x y z rx ry rz per sample, turns continuous frame to frame."""
    turns = rigs.continuous([quat_euler(q) for _, q in samples])
    out = {k: [round(p[i], 6) for p, _ in samples] for i, k in enumerate("xyz")}
    for i, k in enumerate(("rx", "ry", "rz")):
        out[k] = [round(t[i], 6) for t in turns]
    return out
