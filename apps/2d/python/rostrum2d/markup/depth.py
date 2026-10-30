"""Depth in the world: `data-depth="d"` puts an element at a depth the camera reads, for parallax and depth of field.

The camera (film.camera x, y, zoom, rotate) moves a depth-d element as if its offset from the frame's centre were
scaled by d and its zoom raised to the power d: d = 1 is the world (no data-depth), 0 is fixed to the screen,
between is further away, above 1 is in front, moving faster. zoom ** d, not 1 + (zoom - 1)·d: zoom is a ratio, so a
layer's share of it is a share of its logarithm (a 2× push is 1.41× at half depth, a 0.5× pull 0.71×; it never
reaches 0 or turns over, however far in front). Rotate turns every depth alike (the camera rolls, the world doesn't).
Depth of field: camera focus (a depth) and aperture (px of blur per unit of depth away from focus) blur each depth's
layer by |d - focus| · aperture px, in screen pixels.

Where the word is read: on a top-level element of the world, and on a direct child of a top-level <svg> (that svg
becomes stacked copies of itself, one per run of children at one depth, each with every <defs>/<style> kept, as
layers.py does for light). Each run of consecutive elements at one depth gets its own camera box at the frame's
top-left, in paint order, so nothing changes order; elements in normal flow start again at the top-left in each box.
"""
from __future__ import annotations

import re

from .layers import KEEP, _TOKEN

_DEPTH = re.compile(r"""\sdata-depth\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>"']+))""")
_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


def _top(markup: str) -> list[tuple[str, str | None, str]]:
    """The top-level pieces of `markup` in order: (source text, tag name or None for text, start tag's attributes)."""
    out, depth, start, tag, attrs = [], 0, 0, None, ""
    for m in _TOKEN.finditer(markup):
        end, name = m.group(1), m.group(2)
        if depth == 0:
            if name:
                start, tag, attrs = m.start(), name, m.group(3)
                if m.group(4) or name.lower() in _VOID:
                    out.append((m.group(0), tag, attrs))
                else:
                    depth = 1
            elif not end:
                out.append((m.group(0), None, ""))
            continue
        if name and not m.group(4) and name.lower() not in _VOID:
            depth += 1
        elif end:
            depth -= 1
            if depth == 0:
                out.append((markup[start:m.end()], tag, attrs))
    if depth:                                        # an element never closed: the rest is that element
        out.append((markup[start:], tag, attrs))
    return out


def depth_of(attrs: str, default: float = 1.0) -> float:
    """The number in a start tag's data-depth (as the markup has it at this frame, keys applied), else `default`."""
    m = _DEPTH.search(attrs)
    if not m:
        return default
    text = next(g for g in m.groups() if g is not None).strip()
    try:
        return float(text)
    except ValueError:
        raise ValueError(f'data-depth="{text}": a depth is a number (1 the world, 0 fixed to the screen)') from None


def _svg_runs(text: str, attrs: str, d: float) -> list[tuple[float, str]]:
    """A top-level <svg> whose direct children carry data-depth as copies of itself, one per run at one depth."""
    open_end = text.index(">", len("<svg") + len(attrs)) + 1
    close = text.rindex("</")
    kids = _top(text[open_end:close])
    keep = "".join(s for s, tag, _ in kids if tag and tag.lower() in KEEP)
    runs: list[tuple[float, list[str]]] = []
    for s, tag, a in kids:
        if tag and tag.lower() in KEEP:
            continue
        kd = depth_of(a, d) if tag else (runs[-1][0] if runs else d)
        if runs and runs[-1][0] == kd:
            runs[-1][1].append(s)
        else:
            runs.append((kd, [s]))
    return [(kd, text[:open_end] + keep + "".join(body) + "</svg>") for kd, body in runs]


def split(world: str) -> list[tuple[float, str]]:
    """The world as [(depth, markup)] in paint order, consecutive pieces at one depth together."""
    pieces: list[tuple[float, str]] = []
    for s, tag, attrs in _top(world):
        if tag is None:                              # text between elements rides with what comes before it
            pieces.append((pieces[-1][0] if pieces else 1.0, s))
            continue
        d = depth_of(attrs)
        if tag.lower() == "svg" and not _DEPTH.search(attrs) and "data-depth" in s:
            pieces += _svg_runs(s, attrs, d)
        else:
            pieces.append((d, s))
    out: list[tuple[float, str]] = []
    for d, s in pieces:
        if out and out[-1][0] == d:
            out[-1] = (d, out[-1][1] + s)
        else:
            out.append((d, s))
    return out


def transform(cam: dict, w: float, h: float, d: float = 1.0) -> str:
    """The camera's CSS transform for depth d (d = 1: the world's)."""
    x, y, z, r = cam.get("x", w / 2), cam.get("y", h / 2), cam.get("zoom", 1), cam.get("rotate", 0)
    if d != 1:
        x, y, z = w / 2 + (x - w / 2) * d, h / 2 + (y - h / 2) * d, z ** d
    return f"translate({w / 2:.3f}px, {h / 2:.3f}px) scale({z:.5f}) rotate({-r:.4f}deg) translate({-x:.3f}px, {-y:.3f}px)"


def blur_px(cam: dict, d: float = 1.0) -> float:
    """Depth of field: |d - focus| · aperture px; 0 without both."""
    if cam.get("focus") is None or cam.get("aperture") is None:
        return 0.0
    return abs(d - float(cam["focus"])) * float(cam["aperture"])


def camera_wrap(world: str, cam: dict, width: int, height: int) -> str:
    """The world inside the camera: one box (the world has no data-depth), or one box per run of elements at one
    depth, each moved by the camera at its depth and blurred by its distance from focus."""
    w, h = width, height
    box = f"position:absolute; left:0; top:0; width:{w}px; height:{h}px"
    runs = split(world) if "data-depth" in world else [(1.0, world)]
    ident = ' id="rostrum-camera"' if len(runs) == 1 else ""      # ids are one per page
    out = []
    for d, body in runs:
        moved = (f'<div{ident} style="{box}; '
                 f'transform-origin: 0 0; transform: {transform(cam, w, h, d)}">{body}</div>')
        b = blur_px(cam, d)                         # on a still box around the moved one: screen pixels, not world
        out.append(f'<div style="{box}; filter: blur({b:.2f}px)">{moved}</div>' if b > 0 else moved)
    return "".join(out)
