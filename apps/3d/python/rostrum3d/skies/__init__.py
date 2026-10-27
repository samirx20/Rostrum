"""The skies that come with Rostrum3D: real photographed skies (CC0, attributions in the app's README), never moods.
A dome light's `texture` names one as "sky:<key>" ("sky:studio"), so a project keeps working on another computer;
the compiler turns it into this folder's file for the engine (compile.py), so the engine only ever sees a path. A
new sky is one file here and one row in SKIES. The Scene panel's "Sky ▾" lists them (app/screen3d/scene_state.py).
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
PREFIX = "sky:"
SKIES = {          # key: (label, file, where it came from)
    "studio": ("Studio", "studio.hdr", "Poly Haven · Studio Small 09 (Sergej Majboroda), CC0"),
}
START = PREFIX + "studio"          # a new scene's sky


def path(texture: str) -> str:
    """The file the engine reads for a dome's `texture`: a "sky:<key>" is this folder's, anything else as written."""
    if not texture.startswith(PREFIX):
        return texture
    key = texture[len(PREFIX):]
    if key not in SKIES:
        raise ValueError(f'no sky "{key}"; the skies: {", ".join(PREFIX + k for k in SKIES)}')
    return str(HERE / SKIES[key][1])


def label(texture: str) -> str:
    """What the Scene panel calls a dome's texture: the sky's name, "Plain colour" or "Own picture"."""
    if not texture:
        return "Plain colour"
    key = texture[len(PREFIX):] if texture.startswith(PREFIX) else None
    return SKIES[key][0] if key in SKIES else "Own picture"


def choices(texture: str) -> list[dict]:
    """[{value, label}] for the Scene panel's Sky list: every sky here, and what the dome has now if it is none of them."""
    out = [{"value": PREFIX + k, "label": lab} for k, (lab, _f, _src) in SKIES.items()]
    if not any(o["value"] == texture for o in out):
        out.append({"value": texture, "label": label(texture)})
    return out
