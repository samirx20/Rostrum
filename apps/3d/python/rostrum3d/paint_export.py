"""Export painted pictures (SPEC PR6, "UDIM in and out"): a painted mesh's or clay's pictures, the very files the
renderers read (paint_scene's, in the shared cache), written to a folder as UDIM sets a studio tool reads:

    <item>_<channel>.1001.png            one per painted channel (colour, roughness, metal, relief, glow)
    <item>__<material>_<channel>.1001.png   an editable mesh's painted face materials, when it has them
    <item>_paint.json                    the manifest: channel -> its file, its `<UDIM>` set and the material field

Paint is one picture on the item's 0..1 unfold, so each set has the one tile 1001. The pictures are the item's
paint laid over its material's own value (as rendered), not the bare strokes.

    manifest = export(scene, item, "D:/out")   # `scene`: compile.describe's, its paint finished (paint_scene)
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from . import udim
from .paint_fields import CHANNELS

TILE = udim.FIRST


def painted_channels(item: dict) -> list[str]:
    """The channels the item's paint layers paint, in the table's order."""
    used = {layer.get("channel", "colour") for layer in item.get("paints", [])}
    return [c for c in CHANNELS if c in used]


def _materials(scene: dict, item_id: str) -> dict[str, dict]:
    """{"" for the item's own painted material, else the face material's id: its props} in `scene`."""
    own = f"{item_id}__paint"
    out = {}
    for m in scene.get("materials", []):
        if m["id"] == own:
            out[""] = m["props"]
        elif m["id"].startswith(own + "__"):
            out[m["id"][len(own) + 2:]] = m["props"]
    return out


def export(scene: dict, item: dict, folder: str | Path) -> dict:
    """Write `item`'s painted pictures from `scene` into `folder` (made when missing) as UDIM tile 1001 files, and the
    manifest beside them. Loud when the item holds no paint or a picture isn't in the scene (its paint not made)."""
    item_id = item["id"]
    channels = painted_channels(item)
    if not channels:
        raise ValueError(f'{item_id}: has no paint layer, so there is no painted picture to export (paint it first)')
    mats = _materials(scene, item_id)
    if "" not in mats:
        raise ValueError(f"{item_id}: its painted pictures aren't made in this scene (the engine hasn't laid them yet)")
    dest = Path(folder)
    dest.mkdir(parents=True, exist_ok=True)
    manifest = {"item": item_id, "tile": TILE, "uvs": "the item's paint unfold (u, v 0..1)", "channels": {}}
    for face, props in sorted(mats.items()):
        stem = item_id if not face else f"{item_id}__{face}"
        for channel in channels:
            field = CHANNELS[channel][1]
            src = Path(props.get(field) or "")
            if not src.is_file():
                raise ValueError(f'{item_id}: the painted {channel} picture ({field}) is not there: "{src}"')
            name = f"{stem}_{channel}.{TILE}.png"
            shutil.copyfile(src, dest / name)
            key = channel if not face else f"{face}/{channel}"
            manifest["channels"][key] = {"file": name, "set": f"{stem}_{channel}.{udim.TOKEN}.png", "field": field,
                                         "colour": "sRGB" if not CHANNELS[channel][3] else "raw"}
    (dest / f"{item_id}_paint.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
