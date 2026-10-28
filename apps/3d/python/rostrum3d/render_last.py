"""The last finished export of a shot, so a refine export is never quietly worse than the first (round 4 of the 3D gaps: a
drape's refine went out on Storm, without the fabric's sheen, and its reply said nothing). Kept in this process by project,
item and shot, like estimate_learn.

    renderer, cycles, note = keep(k, renderer, cycles, asked)   # before a render_video
    remember(k, renderer, cycles)                                # after one that drew all its frames

A call that names no quality, renderer or samples renders at least as well as the last export: when the shot's own Quality
would be lower, the last export's renderer and samples are used and the note says so. A call that asks for lower is done as
asked, and the note says what it loses. "" when nothing needs saying.
"""
from __future__ import annotations

_LAST: dict[tuple, tuple[str, dict]] = {}
ASKS = ("quality", "renderer", "samples")
LOSES = {"storm": "Storm is a fast draft: no sheen on fabric, no soft light bouncing into the shadows, hard shadow edges",
         "stylized": "Stylized draws the stylized look (lines, halftone, light to colour), not Cycles' real light"}


def key(folder, item, shot: str) -> tuple:
    return (str(folder), item, shot)


def _rank(renderer: str, cycles: dict) -> tuple:
    return (1, cycles.get("samples", 0)) if renderer == "cycles" else (0, 0)


def _says(renderer: str, cycles: dict) -> str:
    return f"cycles, {cycles['samples']} samples" if renderer == "cycles" else renderer


def keep(k: tuple, renderer: str, cycles: dict, args: dict) -> tuple[str, dict, str]:
    """(renderer, its settings, a note) for this export, from what it would use and the shot's last finished export."""
    last = _LAST.get(k)
    if last is None or renderer == "stylized" or last[0] == "stylized" or _rank(renderer, cycles) >= _rank(*last):
        return renderer, cycles, ""
    was = _says(*last)
    if any(a in args for a in ASKS):
        lost = LOSES.get(renderer, "fewer samples: more noise cleaned away, softer detail")
        return renderer, cycles, (f"This export is {_says(renderer, cycles)}, lower than your last export of this shot ({was}): {lost}. "
                                  "Done as asked; leave quality, renderer and samples out to export as the last one did.")
    return last[0], dict(last[1]), (f"Rendered as your last export of this shot ({was}), not the shot's own Quality ({_says(renderer, cycles)}), "
                                    "so this refine is not worse than the first video. Pass quality, renderer or samples to choose.")


def remember(k: tuple, renderer: str, cycles: dict):
    _LAST[k] = (renderer, dict(cycles))
