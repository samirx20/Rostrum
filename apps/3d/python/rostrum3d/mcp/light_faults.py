"""flat_light:<item>, from the shot's picture (3E round 8 canary, "soft key from the left": one added key light gave a
flat, dim cube and the quick look said DONE). The subject is the biggest shape in the picture (not ground-sized); its
lit and dark sides are the bright and dark tenths of its pixels, measured in linear light over its projected box (the
box shrunk a little, its bottom quarter left out: the darkening where it meets the floor is contact, not modelling).
Under FLAT_STOPS between them the subject reads flat. The fault also says when no light of the scene casts a shadow
(a lamp's Casts shadows off, or only the sky), since then nothing grounds it either. Not judged in Stylized pictures
(picked colours, not light) or on a subject too small in the picture to measure.
"""
from __future__ import annotations

import math
from pathlib import Path

from rostrum_core.mcp import faults as F

from rostrum3d.motion_track import Track

FLAT_STOPS = 0.75         # lit tenth over dark tenth of the subject under this many stops: flat
MIN_PX = 900              # a subject covering fewer pixels than this (about 30 × 30) is not measured
SHRINK = 0.08             # each side of the projected box moved in by this share
FOOT = 0.25               # the box's bottom share left out (contact darkening)
BIG_M = 8.0               # a side longer than this is a floor or a wall, not a subject


def _walk(items):
    for it in items:
        yield it
        yield from _walk(it.get("children", []))


def _subject(tr: Track, f: int) -> tuple[str, tuple[float, float, float, float]] | None:
    """(id, (x0, y0, x1, y1) in the camera's pixels, clipped to the picture) of the biggest shown shape in the picture."""
    cam, best = tr.cams[f], None
    for id_ in tr.ids():
        if id_ == "ground" or not tr.shown(id_, f) or tr.fr.values(id_, f).get("backdrop"):
            continue
        solid = tr.row(id_, f)["solid"]
        if not solid or any(max(c[k] for c in solid[0]) - min(c[k] for c in solid[0]) > BIG_M for k in (0, 2)):
            continue
        pts = [cam.project(c) for c in solid[0]]
        if not all(pts):
            continue
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        box = (max(min(xs), 0), max(min(ys), 0), min(max(xs), cam.w), min(max(ys), cam.h))
        area = (box[2] - box[0]) * (box[3] - box[1])
        if box[2] > box[0] and box[3] > box[1] and (best is None or area > best[2]):
            best = (id_, box, area)
    return (best[0], best[1]) if best else None


def _linear(px):
    import numpy as np
    a = px / 255.0
    a = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    return a @ np.array([0.2126, 0.7152, 0.0722])


def spread(png, box, size) -> float | None:
    """Stops between the subject's lit and dark tenths inside `box` (camera pixels; `size` the camera's (w, h)), else None."""
    import numpy as np
    from PIL import Image
    with Image.open(png) as im:
        px = np.asarray(im.convert("RGB"), dtype=float)
    sx, sy = px.shape[1] / size[0], px.shape[0] / size[1]
    x0, y0, x1, y1 = box[0] * sx, box[1] * sy, box[2] * sx, box[3] * sy
    w, h = x1 - x0, y1 - y0
    cut = px[int(y0 + SHRINK * h):int(y1 - FOOT * h), int(x0 + SHRINK * w):int(x1 - SHRINK * w)]
    if cut.shape[0] * cut.shape[1] < MIN_PX:
        return None
    lo, hi = np.percentile(_linear(cut), [10, 90])
    return math.log2(max(hi, 1e-4) / max(lo, 1e-4))


def _casts_shadow(data: dict) -> bool:
    """Whether any shown lamp (not the sky dome) has Casts shadows on."""
    return any(it.get("type") == "light" and it.get("kind") != "dome" and it.get("shadows", True) is not False
               and it.get("visible", True) is not False for it in _walk(data.get("items", [])))


def flat(data: dict, info: dict, f: int, png, folder=None, when: str = "") -> list[dict]:
    """[flat_light:<subject>] when the subject's lit and dark sides are under FLAT_STOPS apart in the picture, else []."""
    if not png or not Path(png).is_file() or not info.get("camera"):
        return []
    try:
        tr = Track(data, info, range(f, f + 1), folder)
        found = _subject(tr, f)
    except (ValueError, KeyError):           # something's size isn't known here (an import), or no camera to look through
        return []
    if not found:
        return []
    id_, box = found
    stops = spread(png, box, (tr.cams[f].w, tr.cams[f].h))
    if stops is None or stops >= FLAT_STOPS:
        return []
    shadow = "" if _casts_shadow(data) else ", and no light casts a shadow (only the sky, or Casts shadows off), so nothing grounds it"
    return [F.fault(f"flat_light:{id_}",
                    f"flat: {id_}'s lit and dark sides differ by {stops:.1f} stops in the picture (under {FLAT_STOPS:g}){shadow}",
                    "make the key rake across what the camera sees: move it to the side and lower (about level with the top of "
                    f"{id_}, beside it rather than in front), or turn {id_} / the camera so two faces show; lower the fill (the "
                    "sky's exposure, or a fill light's brightness) so the far side drops about 2 stops under the key; keep the "
                    "key's shadows on (shadows=True) and high enough to drop a shadow beside it; if flat is meant, keep it", when)]
