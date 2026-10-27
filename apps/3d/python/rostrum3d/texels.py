"""Which texel of which item each pixel of a camera's picture sees: the engine's `texels` request (ENGINE_CONTRACT.md
› Texels), read into arrays. The single source of truth for painting from the view, projecting a picture and coverage.

The engine writes raw little-endian float32, rows top first, 4 a pixel: u, v (the surface's `st`, NaN where none),
item (index into the reply's `items`, -1 = nothing / no item), distance (metres from the eye, -1 = nothing).

`ask(req) -> reply` below is an engine's `texels_reply` (rostrum3d.engine.Engine or the window's ItemEngine): `req` is
the request's fields (camera or eye + target + fov, frame, width, height, file). The engine must hold the scene the
picture is of (ensure_scene first).
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Callable

import numpy as np

from rostrum_core.cache import CACHE, cache_key

KIND = "texels"
VERSION = "rostrum3d-texels@1+contract-1.22"   # bump with the engine's texels request (its file or how it finds u, v)
FILE, REPLY = "texels.bin", "reply.json"
LOOKS = {"material", "materials"}              # what a scene's look is, not its shape: texels never depend on it
LATER = "paintLater"                           # paint_scene.LATER: paint pictures still to make, a look too

Ask = Callable[[dict], dict]


class Picture:
    """A texel picture: `uv` (h, w, 2) float32 NaN where none, `item` (h, w) int16 -1 = none, `items` the item ids,
    `distance` (h, w) float32 -1 = none."""

    def __init__(self, data: np.ndarray, items: list[str]):
        h, w, _ = data.shape
        self.width, self.height = w, h
        self.uv = data[..., :2]
        self.item = data[..., 2].astype(np.int16)
        self.items = list(items)
        self.distance = data[..., 3]

    def of(self, item_id: str) -> np.ndarray:
        """(h, w) bool: the pixels showing that item (all False when it isn't seen)."""
        if item_id not in self.items:
            return np.zeros((self.height, self.width), bool)
        return self.item == self.items.index(item_id)


def read(reply: dict) -> Picture:
    """The picture an engine's texels reply wrote (`file`, `width`, `height`, `items`). Loud when the file is missing
    or not the size the reply says."""
    w, h, path = int(reply["width"]), int(reply["height"]), Path(reply["file"])
    if not path.is_file():
        raise ValueError(f"texels: the engine said done but there is no file {path}")
    data = np.fromfile(path, "<f4")
    if data.size != w * h * 4:
        raise ValueError(f"texels: {path} holds {data.size} floats; a {w} x {h} picture is {w * h * 4} "
                         "(cut short or written by another version)")
    return Picture(data.reshape(h, w, 4), reply.get("items", []))


def _shape(v):
    if isinstance(v, dict):
        return {k: _shape(x) for k, x in v.items() if k not in LOOKS}
    if isinstance(v, list):
        return [_shape(x) for x in v]
    return v


def geometry_key(scene: dict) -> str:
    """A hash of the scene without its materials and paint pictures: what a texel picture depends on (the shapes,
    their places and unfoldings, the cameras, the frames). Repainting or changing a material keeps it."""
    shape = _shape({k: v for k, v in scene.items() if k != LATER})
    return hashlib.sha256(json.dumps(shape, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def fetch(ask: Ask, req: dict) -> Picture:
    """Ask for a picture and read it. Without a `file`, a temporary one, read and removed."""
    if req.get("file"):
        return read(ask(req))
    fd, tmp = tempfile.mkstemp(suffix=".texels.bin")
    os.close(fd)
    try:
        return read(ask({**req, "file": tmp}))
    finally:
        os.unlink(tmp)


def cached(scene: dict, req: dict, ask: Ask | None = None) -> Picture | None:
    """The picture for `req` (no `file`: the cache keeps it) on `scene`'s geometry, from the shared cache (kind
    "texels"), else asked with `ask` (the engine holding `scene`) and kept. None when it isn't kept and no `ask`."""
    body = {k: v for k, v in req.items() if k != "file"}
    key = cache_key(KIND, VERSION, [geometry_key(scene)], body)
    folder = CACHE.get(KIND, key)
    if folder is None:
        if ask is None:
            return None

        def make(tmp: Path):
            reply = ask({**body, "file": str(tmp / FILE)})
            read({**reply, "file": str(tmp / FILE)})                      # checked before it is kept
            (tmp / REPLY).write_text(json.dumps({k: reply[k] for k in ("width", "height", "items")}), encoding="utf-8")
        folder = CACHE.put(KIND, key, make, {"req": body})
    meta = json.loads((folder / REPLY).read_text(encoding="utf-8"))
    return read({**meta, "file": str(folder / FILE)})
