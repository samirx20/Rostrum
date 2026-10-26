"""Which body part a layer is, read from its name ("upper arm L", "Forearm_R", "leftHand", "thigh", "head"): the one
place that knows the words (RIG.md › Bones from part names). Pure; `rig.guess_bones` (guess.py) builds on it.

    part("upper arm L") -> ("upperarm", "L")      part("mouth A") -> ("face", "")      part("cloud") -> None
"""
from __future__ import annotations

import re
from functools import lru_cache

from rostrum_core.names import tokens

# (role, words): the first role whose words appear in the name, as whole words, wins (so "upper arm" before "arm").
ROLES = [
    ("forearm", ("forearm", "lower arm", "lowerarm", "fore arm")),
    ("upperarm", ("upper arm", "upperarm", "arm")),
    ("hand", ("hand", "fist", "palm")),
    ("shin", ("shin", "calf", "lower leg", "lowerleg")),
    ("thigh", ("thigh", "upper leg", "upperleg", "leg")),
    ("foot", ("foot", "feet", "shoe", "boot")),
    ("neck", ("neck",)),
    ("head", ("head", "skull")),
    ("hip", ("hip", "hips", "pelvis")),
    ("torso", ("torso", "body", "chest", "trunk", "belly", "spine")),
    ("face", ("mouth", "mouths", "eye", "eyes", "brow", "brows", "nose", "ear", "ears", "hair", "face", "lip", "lips",
              "pupil", "blink", "jaw")),
]
LIMBS = {"arm": ("upperarm", "forearm", "hand"), "leg": ("thigh", "shin", "foot")}
SIDES = {"l": "L", "left": "L", "lt": "L", "r": "R", "right": "R", "rt": "R"}
_SAYS = [(role, re.compile(" (?:" + "|".join(map(re.escape, says)) + ") ")) for role, says in ROLES]   # one look per role
WORDS = {"upperarm": "upper arm", "forearm": "forearm", "hand": "hand", "thigh": "thigh", "shin": "shin",
         "foot": "foot", "neck": "neck", "head": "head", "torso": "body"}


@lru_cache(maxsize=4096)
def part(name: str) -> tuple[str, str] | None:
    """(role, side "L" / "R" / "") of a layer named like a body part, else None. Kept per name: the action list asks
    it of every picked layer on each pick (Make rig first), 200 layers ~4-10 ms looked at afresh."""
    words = tokens(name)
    side = next((SIDES[w] for w in words if w in SIDES), "")
    rest = " " + " ".join(w for w in words if w not in SIDES) + " "
    return next(((role, side) for role, says in _SAYS if says.search(rest)), None)


def bodylike(names) -> bool:
    """Named like a body: at least two limb or trunk parts (a face alone is not a skeleton). `names` may be lazy: it
    stops at the second part."""
    found = 0
    for name in names:
        p = part(name)
        if p and p[0] != "face":
            found += 1
            if found == 2:
                return True
    return False
