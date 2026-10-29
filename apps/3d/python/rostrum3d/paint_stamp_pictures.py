"""A stamp's picture (paint.stamp), laid whole: the painting kit's dab is round and would clip a square picture's
corners, so a stamp uses a **padded copy**: the picture fitted into a square of its longest side, centred on a square
PAD times as wide, the padding see-through (flat). The dab is then PAD × the stamp's size (the op's `fit`), so the
picture itself measures `size` and lies wholly inside the round dab (its corners at 0.71 / PAD = 94 % of its radius).

The copy is made once and kept in the project like any loaded picture (rostrum_paint.library: content-keyed, its id
from its content), with `media/brushtip/stamps.json` saying which tips are padded copies and of what, so a picture is
padded once however often it is stamped. What a copy holds is the amount the stamp raises, as its opacity:
- a picture file: its brightness (white raised most, black flat), or its opacity when it has see-through parts;
- a tip picture already in the project (loaded for a brush): what the kit paints of it (dark, or opaque).
The built-in tips (sponge, speckle, streaks, ragged, charcoal) are textures that fill the dab: used as they are (fit 1).
"""
from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

import numpy as np
from rostrum_core import project
from rostrum_core.cache import file_hash
from rostrum_core.errors import RostrumError, codes
from rostrum_core.storage import write_atomic
from rostrum_paint import library, pictures

PAD = 1.5
INDEX = Path("media") / "brushtip" / "stamps.json"      # {"of": {"file:<hash>" | "tip:<id>": padded tip id}}


def _index(folder) -> dict:
    f = Path(folder) / INDEX
    return json.loads(f.read_text("utf-8")) if f.is_file() else {"of": {}}


def _remember(folder, key: str, tip: str):
    data = _index(folder)
    data["of"][key] = tip
    (Path(folder) / INDEX).parent.mkdir(parents=True, exist_ok=True)
    write_atomic(Path(folder) / INDEX, json.dumps(data, indent=1))


def padded(folder) -> set[str]:
    """The project's padded stamp tips."""
    return set(_index(folder)["of"].values()) if folder else set()


def hidden(folder) -> set[str]:
    """Tips a stamp's Picture list leaves out: the padded copies of brush tips (their source is listed instead)."""
    return {v for k, v in _index(folder)["of"].items() if k.startswith("tip:")} if folder else set()


def _amount(path: Path, relief: bool) -> np.ndarray:
    """0..1 per pixel: how much the stamp raises there (relief: a file's brightness) or the kit's reading (dark)."""
    from PIL import Image, UnidentifiedImageError
    try:
        im = Image.open(path)
        im.load()
    except (OSError, UnidentifiedImageError) as e:
        raise RostrumError(codes.BAD_ARGUMENT, "paint.stamp", str(path), f"can't be read as a picture: {e}") from e
    rgba = np.asarray(im.convert("RGBA"), np.float32) / 255
    lum = np.asarray(im.convert("L"), np.float32) / 255
    if rgba[..., 3].min() < 0.99:
        return rgba[..., 3]
    return lum if relief else 1 - lum


def _keep(folder, amount: np.ndarray, name: str, key: str) -> str:
    """The padded copy of `amount` kept in the project; its tip id (remembered under `key`)."""
    from PIL import Image
    h, w = amount.shape
    side = math.ceil(max(h, w) * PAD)
    alpha = np.zeros((side, side), np.uint8)
    y0, x0 = (side - h) // 2, (side - w) // 2
    alpha[y0:y0 + h, x0:x0 + w] = np.clip(np.rint(amount * 255), 0, 255).astype(np.uint8)
    rgba = np.dstack([np.full((side, side, 3), 255, np.uint8), alpha])
    with tempfile.TemporaryDirectory(prefix="rostrum-stamp-") as tmp:
        out = Path(tmp) / f"{name}.png"
        Image.fromarray(rgba, "RGBA").save(out)
        tip = library.load(folder, out, "tip", name)["id"]
    _remember(folder, key, tip)
    return tip


def prepare(folder, picture: str) -> tuple[str, float]:
    """(tip id, fit) for a stamp's `picture`: a built-in tip as it is (1); a padded tip as it is (PAD); a project's
    tip or a picture file: its padded copy, made the first time (PAD). Loud for what is neither."""
    if picture in pictures.TEXTURES and picture != "none":
        return picture, 1.0
    if not folder:
        raise RostrumError(codes.BAD_ARGUMENT, "paint.stamp", f'picture "{picture}"', "a picture other than the "
                           "built-in tips needs the scene saved in a project, where the picture is kept",
                           [t for t in pictures.TEXTURES if t != "none"], hint="Save the scene first.")
    library.use_project(folder)
    of = _index(folder)["of"]
    if picture in of.values():
        return picture, PAD
    rows = {r["id"]: r for r in project.items(folder, library.KIND["tip"])}
    if picture in rows:
        key = f"tip:{picture}"
        if key not in of:
            of[key] = _keep(folder, _amount(Path(folder) / rows[picture]["file"], False), rows[picture]["name"], key)
        return of[key], PAD
    src = Path(picture)
    src = src if src.is_absolute() else Path(folder) / src
    if not src.is_file():
        raise RostrumError(codes.NOT_FOUND, "paint.stamp", f'picture "{picture}"', f"is neither a tip picture nor a "
                           f"file ({src})", [c["value"] for c in library.choices("tip") if c["value"] != "none"],
                           hint="Give a picture file (PNG, JPEG …) or a tip picture's name.")
    key = f"file:{file_hash(src)[:16]}"
    if key not in of:
        of[key] = _keep(folder, _amount(src, True), src.stem, key)
    return of[key], PAD
