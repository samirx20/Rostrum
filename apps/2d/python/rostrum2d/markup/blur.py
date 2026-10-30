"""Per-element motion blur: `data-blur="off"` draws an element sharp, `data-blur="<degrees>"` gives it its own shutter,
while the rest of the frame keeps the film's blur (film.samples).

Each blur sample is the whole stage at a moment across the shutter. An element with its own shutter is swapped, in
every sample, for itself as drawn at its own moment: the frame's moment for "off", the same fraction of its own
(shorter or longer) shutter for a number. Its own keys and content are held; a moving parent still carries it.
Elements match between moments by order (the k-th `data-blur` element in each), so ids are not needed.
"""
from __future__ import annotations

import re

_TAG = re.compile(r"<!--.*?-->|<(/?)([A-Za-z][\w:.-]*)((?:[^>\"']|\"[^\"]*\"|'[^']*')*?)(/?)>", re.S)
_BLUR = re.compile(r"\sdata-blur\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)")
_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


def parts(markup: str) -> list[tuple[int, int, str]]:
    """The outermost elements carrying data-blur: (start, end, value) spans of their whole markup, in order."""
    out: list[tuple[int, int, str]] = []
    stack: list[tuple[str, int, str | None]] = []      # (tag, start, data-blur value when this element has one)
    inside = 0                                          # open elements with data-blur
    for m in _TAG.finditer(markup):
        close, tag, attrs, selfclose = m.group(1), m.group(2), m.group(3), m.group(4)
        if tag is None:
            continue
        name = tag.lower()
        if close:
            for i in range(len(stack) - 1, -1, -1):
                if stack[i][0] == name:
                    for _, start, value in reversed(stack[i:]):
                        if value is not None:
                            inside -= 1
                            if inside == 0:
                                out.append((start, m.end(), value))
                    del stack[i:]
                    break
            continue
        b = _BLUR.search(attrs)
        value = b.group(1).strip("\"'").strip() if b else None
        if selfclose or name in _VOID:
            if value is not None and inside == 0:
                out.append((m.start(), m.end(), value))
            continue
        stack.append((name, m.start(), value))
        if value is not None:
            inside += 1
    return out


def degrees(value: str) -> float | None:
    """The element's own shutter in degrees: "off" (or 0) -> 0; a number -> it; anything else -> None (the film's)."""
    v = value.strip().lower().removesuffix("deg")
    if v in ("off", "none", "false"):
        return 0.0
    try:
        return max(0.0, float(v))
    except ValueError:
        return None


def swap(markup: str, fraction: float, at) -> str:
    """`markup` (a blur sample at `fraction` of the shutter, -0.5..0.5) with each data-blur element taken from
    `at(frames)`, the stage markup that many frames (a fraction) after the frame's moment."""
    mine = parts(markup)
    if not mine:
        return markup
    out, pos = [], 0
    for k, (start, end, value) in enumerate(mine):
        deg = degrees(value)
        if deg is None:
            continue
        source = at(deg / 360 * fraction)
        theirs = parts(source)
        if k >= len(theirs):
            continue
        s, e, _ = theirs[k]
        out += [markup[pos:start], source[s:e]]
        pos = end
    out.append(markup[pos:])
    return "".join(out)
