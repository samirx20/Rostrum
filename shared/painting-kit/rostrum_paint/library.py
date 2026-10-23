"""The project's own tip and paper pictures (painting design §5, P5): a picture a person or an agent loads is kept as
a project item (rostrum_core.project.add_file: copied into the project's media/, a row in project.json, its id from
its content). A stroke names the item id, never a file path, so a moved project still paints. The decoded picture
is made once into the shared content-keyed cache (kind "paint-picture") and read from there.

One list for screens and agents: `choices("tip")` / `choices("paper")` are the built-in pictures, then the project's
own; fields.py keeps the brush settings' options to it (`listen`), so the Edit brush page lists both.
A stroke naming an item that is not in the open project fails loudly, naming it.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from rostrum_core import project
from rostrum_core.cache import CACHE, cache_key
from rostrum_core.errors import RostrumError, codes

from . import pictures

KIND = {"tip": "brushtip", "paper": "paper"}          # the item kind each is kept as
ENGINE = "rostrum-paint-picture@1"                    # how a file becomes a picture; bump when _decode changes
_own: dict[str, dict] = {}                             # item id -> its project.json row + "as" + "path"
_listeners: list = []
_arrays: dict[str, np.ndarray] = {}
_seen: list = [None]                                  # (folder, project.json's change time) last read
generation = 0                                        # counts changes of the choices (a screen re-lays its rows)


def listen(fn):
    _listeners.append(fn)
    fn()


def use_project(folder) -> None:
    """The open project's own pictures become choices (the last project used wins; None = no project). Cheap to
    call before every render: project.json is read again only when it changed."""
    meta = Path(folder) / "project.json" if folder else None
    stamp = (str(folder), meta.stat().st_mtime_ns if meta and meta.is_file() else 0)
    if stamp == _seen[0]:
        return
    global generation
    _seen[0], generation = stamp, generation + 1
    _own.clear()
    for as_, kind in KIND.items():
        for it in project.items(folder, kind) if folder else ():
            _own[it["id"]] = {**it, "as": as_, "path": Path(folder) / it["file"]}
    for fn in _listeners:
        fn()


def load(folder, path, as_: str, name: str = "") -> dict:
    """Keep the picture at `path` in the project as a tip or a paper; its item row. A file that isn't a picture
    is refused before anything is added."""
    if as_ not in KIND:
        raise RostrumError(codes.BAD_ARGUMENT, "picture.load", f'as "{as_}"', "must be tip or paper", list(KIND))
    _decode(Path(path), as_)
    row = project.add_file(folder, KIND[as_], name, path)
    use_project(folder)
    return row


def choices(as_: str) -> list[dict]:
    """[{value, label}]: the built-in pictures first, then the project's own (labelled by their item names)."""
    built = pictures.TEXTURES if as_ == "tip" else pictures.PAPERS
    return [{"value": v, "label": v.capitalize()} for v in built] + [
        {"value": i, "label": r["name"]} for i, r in _own.items() if r["as"] == as_]


def picture(item_id: str, as_: str) -> np.ndarray:
    """The decoded picture of the project's own item `item_id`, from the shared cache (made on first use)."""
    row = _own.get(item_id)
    if row is None or row["as"] != as_:
        raise RostrumError(codes.NOT_FOUND, "painting", f'{as_} picture "{item_id}"',
                           "is not an item of the open project (it was removed, or the stroke came from another project)",
                           [i for i, r in _own.items() if r["as"] == as_], "Load the picture again, or pick another.")
    key = cache_key("paint-picture", ENGINE, [row["hash"]], {"as": as_})
    if key not in _arrays:
        if not row["path"].is_file():
            raise RostrumError(codes.NOT_FOUND, "painting", f'{as_} picture "{row["name"]}" ({item_id})',
                               f'its file {row["file"]} is missing from the project')
        entry = CACHE.get("paint-picture", key) or CACHE.put(
            "paint-picture", key, lambda d: np.save(d / "picture.npy", _decode(row["path"], as_)),
            {"engine": ENGINE, "item": item_id, "as": as_})
        _arrays[key] = np.ascontiguousarray(np.load(entry / "picture.npy"), np.float32)
    return _arrays[key]


def _decode(path: Path, as_: str) -> np.ndarray:
    """A tip: the picture fitted into the dab square, paint where it is dark (or opaque, when it has see-through
    parts). A paper: the middle square as a tile, its light parts the raised tooth."""
    from PIL import Image, UnidentifiedImageError
    try:
        im = Image.open(path)
        im.load()
    except (OSError, UnidentifiedImageError) as e:
        raise RostrumError(codes.BAD_ARGUMENT, "picture.load", str(path), f"can't be read as a picture: {e}") from e
    rgba = im.convert("RGBA")
    lum = rgba.convert("L")
    n = pictures.TIP_N if as_ == "tip" else pictures.PAPER_N
    if as_ == "paper":
        s = min(lum.size)
        box = ((lum.width - s) // 2, (lum.height - s) // 2, (lum.width + s) // 2, (lum.height + s) // 2)
        return np.asarray(lum.crop(box).resize((n, n), Image.LANCZOS), np.float32) / 255
    alpha = np.asarray(rgba.getchannel("A"), np.float32) / 255
    v = alpha if alpha.min() < 0.99 else 1 - np.asarray(lum, np.float32) / 255
    k = n / max(im.size)
    w, h = max(1, round(im.width * k)), max(1, round(im.height * k))
    fit = np.asarray(Image.fromarray(v).resize((w, h), Image.LANCZOS), np.float32)
    out = np.zeros((n, n), np.float32)
    out[(n - h) // 2:(n - h) // 2 + h, (n - w) // 2:(n - w) // 2 + w] = np.clip(fit, 0, 1)
    return out
