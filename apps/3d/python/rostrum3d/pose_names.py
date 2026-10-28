"""Part names for posing a clay figure from a script (script_pose.py): a joint name ("hand.R", "head"), the figure's own
sides in words ("right hand", "left foot"), or the picture's sides ("picture-left hand": whichever hand the shot's camera
sees on the left of the picture at that time). An unknown name is a ValueError listing the names that exist."""
from __future__ import annotations

SIDED = ("hand", "forearm", "arm", "foot", "toe", "leg", "shin")
OWN = {"left": "L", "right": "R"}
PICTURE = ("picture-left", "picture-right")


def words(name: str) -> tuple[str, str | None]:
    """(the part, its side: "L" / "R" / "picture-left" / "picture-right" / None) of a name in words; a joint name
    ("hand.R") comes back as it is, with no side."""
    if "." in name:
        return name, None
    w = name.strip().lower().replace("_", " ").replace("picture left", "picture-left").replace("picture right", "picture-right").split()
    if len(w) == 2 and (w[0] in OWN or w[0] in PICTURE):
        return w[1], OWN.get(w[0], w[0])
    return " ".join(w) or name, None


def choices(joints: list[str]) -> str:
    """The names a figure's parts go by, for an error or a hint."""
    sided = sorted({j[:-2] for j in joints if j.endswith((".L", ".R"))})
    p = "hand" if {"arm", "forearm", "hand"} & set(sided) else sided[0] if sided else ""
    eg = f'"left {p}" / "right {p}" (its own sides), "picture-left {p}" / "picture-right {p}" ' \
         "(as the shot's camera sees it)" if p else ""
    return ", ".join(joints) + (f"; or in words: {eg}" if eg else "")


def picture_left(cam_world, points: dict) -> list[str]:
    """The names in `points` ({name: world point}) from the picture's left to its right, as the camera (its world
    transform: it looks down its own −Z, its +X is the picture's right) sees them."""
    eye, lin = cam_world[1], cam_world[0]
    right = [lin[0][0], lin[1][0], lin[2][0]]
    return sorted(points, key=lambda n: sum((p - e) * r for p, e, r in zip(points[n], eye, right)))


def resolve(name: str, rig, owner: str, seen=None) -> int:
    """The bone (Rig index) a part name means. `seen(part)` -> [joint names left to right in the picture], or None
    with no camera. Rig.find takes joint names, Humanoid names, and a short limb's last bone for its hand / foot."""
    part, side = words(name)
    joints, asked = [j for j in rig.joint if j], name
    if side in ("L", "R"):
        name = f"{part}.{side}"
    elif side in PICTURE and any(f"{part}.{s}" in joints or _limb(part, s, joints) for s in "LR"):
        if seen is None:
            raise ValueError(f'{owner}: "{asked}" needs the shot camera to know which side is the picture left; make '
                             f'camera() and shot(camera=) before posing, or say "left {part}" / "right {part}" (the '
                             "figure's own sides)")
        order = seen(part)
        name = order[0] if side == "picture-left" else order[-1]
    elif side is None and part in joints:
        name = part
    try:
        return rig.find(name)
    except ValueError:
        raise ValueError(f'{owner}: no part "{asked}"; its parts: {choices(joints)}') from None


def _limb(part: str, side: str, joints: list[str]) -> bool:
    """A short limb stands for its hand / foot (Rig.find): an arm.R with no hand.R still has a right hand."""
    return part in SIDED and any(j.endswith("." + side) and j[:-2] in ("arm", "forearm", "leg", "shin") for j in joints)
