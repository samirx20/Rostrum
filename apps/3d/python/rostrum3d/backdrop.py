"""backdrop_edge:<dome>, a fault of faults.py's list: a photographed sky the camera sees (a dome with a picture and
`seenByCamera` on) shows in the picture past every floor, wall and thing in it, so its room's walls, lamps and edges
cross the shot (round 5 of the 3D gaps, Drape: the Studio photo's black band and grey panel along the top of a low camera).
The start sky is not seen by the camera (start_scene.py); this names the case where a script or a person turned it on.
Measured with rays through a grid of the picture against the things' boxes: nothing is rendered.
"""
from __future__ import annotations

from rostrum_core.mcp import faults as F

RAYS = 9                # RAYS × RAYS rays over the picture
SHARE = 0.02            # this share of the rays or more seeing the photo is a fault (one ray of 81 is a sliver)


def _seen_photo(items: dict) -> str | None:
    """The id of a dome the camera sees with a picture on it, or None."""
    return next((i for i, n in items.items() if n.get("type") == "light" and n.get("kind") == "dome" and n.get("texture")
                 and n.get("seenByCamera", True) and n.get("visible", True) is not False), None)


def _hits(eye, d, lo, hi) -> bool:
    """Whether the ray eye + t·d (t > 0) passes through the box lo–hi (a flat box, like a floor, counts)."""
    t0, t1 = 0.0, float("inf")
    for k in range(3):
        if abs(d[k]) < 1e-12:
            if not lo[k] - 1e-6 <= eye[k] <= hi[k] + 1e-6:
                return False
            continue
        a, b = (lo[k] - 1e-6 - eye[k]) / d[k], (hi[k] + 1e-6 - eye[k]) / d[k]
        t0, t1 = max(t0, min(a, b)), min(t1, max(a, b))
        if t0 > t1:
            return False
    return True


def backdrop_edge(track, info: dict, boxes: dict, check: list[int]) -> list[dict]:
    """The fault when the seen sky photo fills SHARE of the picture or more on the middle checked frame."""
    from .faults import when
    dome = _seen_photo(track.fr.items)
    f = check[len(check) // 2]
    cam = track.cams.get(f)
    if dome is None or cam is None:
        return []
    solids = [b[f][0] for b in boxes.values()]
    misses, top = 0, 0
    for a in range(RAYS):
        for b in range(RAYS):
            u, v = -1 + 2 * (a + 0.5) / RAYS, 1 - 2 * (b + 0.5) / RAYS
            d = [-cam.back[k] + u * cam.tan_w * cam.right[k] + v * cam.tan_h * cam.up[k] for k in range(3)]
            if not any(_hits(cam.eye, d, lo, hi) for lo, hi in solids):
                misses += 1
                top = max(top, RAYS - b)
    if misses < SHARE * RAYS * RAYS:
        return []
    where = "across the top" if top <= RAYS // 2 else "over much"
    return [F.fault(f"backdrop_edge:{dome}", f"the sky photo ({dome}) shows {where} of the picture past the floor: its room's "
                    f"walls, lamps and edges cross the shot (about {100 * misses // (RAYS * RAYS)} % of it)",
                    f'turn the photo off for the camera: edit("{dome}", seenByCamera=False) (it still lights and reflects; '
                    "the shot's background colour shows there, so set it near the floor's), or tilt the camera down; "
                    "if the photo is meant to be seen, keep it", when(info, f))]
