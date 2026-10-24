"""What the document refuses about frames (apps/2d/FRAME.md › Refused), run by kind.check: every scene holds exactly
one frame, in its own layers (never inside a group or rig), with a zoom above 0 in every key (a still zoom has its
field's own range). Deleting, adding a second, grouping or copying the frame is refused by these too; the layer
operations that never apply to it take only fields.PLACED, so they refuse it by name."""
from __future__ import annotations

from . import TYPE


def _nested(holder: dict, problems: list):
    for l in holder.get("layers", []):
        if l.get("type") == TYPE:
            problems.append(f'{l["id"]}: a frame belongs to its scene, not inside {holder["type"]} "{holder["id"]}"')
        _nested(l, problems)


def problems(data: dict, items=None) -> list[str]:
    """Each scene's frame count (always: a scene's own layers are few), the zoom keys of changed frames, and, on
    open (`items` None), frames inside groups or rigs."""
    out = []
    for comp in data.get("comps", []):
        n = sum(1 for l in comp.get("layers", []) if l.get("type") == TYPE)
        if n != 1:
            out.append(f'scene "{comp["id"]}" has {n} frames: a scene has exactly one (it is what is exported, and its '
                       f"camera){'; it is made with the scene and can be moved, keyed or locked, never deleted' if n == 0 else ''}")
        if items is None:
            for l in comp.get("layers", []):
                _nested(l, out)
    for f in (i for i in (items or [l for c in data.get("comps", []) for l in c.get("layers", [])]) if i.get("type") == TYPE):
        for k in f.get("keys", []):
            if k.get("prop") == "zoom" and not (isinstance(k.get("v"), (int, float)) and k["v"] > 0):
                out.append(f'{f["id"]}.zoom at {k.get("t")} s: {k.get("v")} is not above 0 (a frame\'s zoom must be above 0)')
    return out
