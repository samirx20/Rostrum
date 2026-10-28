"""What a video, export or look shows of the fall over the frames it covers (the cut), beside fall_view's "is the fall
seen": the cut opens after the drop began or after it landed ("the video opens mid-drop"), a thing is already moving at
the shot's first frame, and everything has settled long before the cut ends (a dead stretch). One plain line each, with
the fix, from `fall_view.views` rows. Round 3 of the 3D gaps: a refine cut of a drape started mid-drop and nothing said so.
"""
from __future__ import annotations

MIN_TAIL_S = 2.0       # a still stretch at least this long ...
MIN_TAIL_SHARE = 0.4   # ... and at least this share of the cut is named
_CUT = "start the cut at or before {a:.1f} s (render_video `start`, the shot's start)"
_TAIL = ("shorten the cut to end soon after {m:.1f} s (render_video `end`, the shot's end), or slow the fall (a lighter cloth: "
         "clothWeight; a later fallStart; a higher drop), or key the camera or other things so the shot has something to show")


def cut_lines(rows: list[dict], f0: int, f1: int, s0: int, fps: float) -> list[str]:
    """Plain lines (each with its fix) about frames f0–f1 of a shot starting at frame s0; rows from fall_view.views."""
    t = lambda f: (f - s0) / fps  # noqa: E731
    movers = [r for r in rows if r.get("moving")]
    out = []
    for r in movers:
        a, b = r["drop"]
        who = f"{r['item']} ({'cloth' if r['kind'] == 'cloth' else 'fall'})"
        if f0 > b:
            out.append(f"{who}: its drop is over ({t(a):.1f}–{t(b):.1f} s) before this cut starts at {t(f0):.1f} s: the video opens on it "
                       f"already fallen. To show it fall, {_CUT.format(a=t(a))}.")
        elif f0 > a:
            out.append(f"{who}: this cut starts at {t(f0):.1f} s, {t(f0) - t(a):.1f} s into its drop ({t(a):.1f}–{t(b):.1f} s): the video opens "
                       f"mid-drop. To show it from the start, {_CUT.format(a=t(a))}.")
        elif r.get("underway") and f0 == s0:
            out.append(f"{who} is already moving at the first frame, so the shot opens with it mid-fall. Give it a moment first (fallStart, "
                       "'Falls from'), or start it higher.")
    if not movers:
        return out
    last = max(r["moving"][1] for r in movers)
    if f0 > last:
        out.append(f"Everything settled by {t(last):.1f} s, before this cut starts at {t(f0):.1f} s: nothing falling or draping moves in it "
                   "(only the camera, if it moves).")
        return out
    tail, length = (f1 - last) / fps, (f1 - f0 + 1) / fps
    if tail >= max(MIN_TAIL_S, MIN_TAIL_SHARE * length):
        out.append(f"Everything settles at {t(last):.1f} s: the last {tail:.1f} s of this {length:.1f} s cut don't move (only the camera, if it "
                   f"moves); {_TAIL.format(m=t(last))}.")
    return out
