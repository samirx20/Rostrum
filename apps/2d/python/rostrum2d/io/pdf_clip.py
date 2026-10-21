"""PDF clip paths → 2D's track matte (fields.py "matte": a layer is seen only where a layer beside it is drawn; the
matte layer itself is not shown). A run of neighbouring objects under the same clip goes in one group with that clip's
shape as the group's matte; nested clips nest the groups. A clip that is a plain rectangle holding the whole object
(the page-sized clip most exporters write) changes nothing and is dropped, not reported."""
from __future__ import annotations

from .. import pathdata as PD


def px_clips(clips, to_px) -> tuple:
    """Clips (rule, y-up segments) → (rule, px commands, key) outermost first; the key is equal for equal shapes."""
    out = []
    for rule, segs in clips:
        cmds = PD.transformed(list(segs), to_px)
        out.append((rule, tuple(cmds), hash((rule, tuple(cmds)))))
    return tuple(out)


def is_rect(cmds) -> tuple | None:
    """(x0, y0, x1, y1) when the commands are one axis-aligned rectangle, else None."""
    pts = [c[1:3] for c in cmds if c[0] in "ML"]
    if len(pts) not in (4, 5) or any(c[0] == "C" for c in cmds) or len(cmds) > 6:
        return None
    if len(pts) == 5 and pts[4] != pts[0]:
        return None
    xs, ys = sorted({round(p[0], 3) for p in pts}), sorted({round(p[1], 3) for p in pts})
    return (xs[0], ys[0], xs[-1], ys[-1]) if len(xs) == 2 and len(ys) == 2 else None


def needed(clips, box, margin: float = 0.0) -> tuple:
    """The clips that change how an object with this box (x, y, w, h) looks."""
    keep = []
    for c in clips:
        r = is_rect(c[1])
        inside = r and r[0] <= box[0] - margin + 1e-3 and r[1] <= box[1] - margin + 1e-3 \
            and r[2] >= box[0] + box[2] + margin - 1e-3 and r[3] >= box[1] + box[3] + margin - 1e-3
        if not inside:
            keep.append(c)
    return tuple(keep)


def box_of(node) -> list:
    if node["type"] != "group":
        return node["box"]
    kids = [box_of(k) for k in node["layers"]]
    x0, y0 = min(b[0] for b in kids), min(b[1] for b in kids)
    return [x0, y0, max(b[0] + b[2] for b in kids) - x0, max(b[1] + b[3] for b in kids) - y0]


def bounds(clips) -> tuple | None:
    """The box all the clips share (x0, y0, x1, y1), or None with no clips."""
    boxes = [PD.bounds(list(c[1])) for c in clips]
    if not boxes:
        return None
    return max(b[0] for b in boxes), max(b[1] for b in boxes), min(b[2] for b in boxes), min(b[3] for b in boxes)


def wrap(items, name) -> list[dict]:
    """[(node, clips)] in painting order → tree nodes: unclipped as they are, clipped ones in groups with a matte beside."""
    out, i = [], 0
    while i < len(items):
        node, clips = items[i]
        if not clips:
            out.append(node)
            i += 1
            continue
        j = i
        while j < len(items) and items[j][1] and items[j][1][0][2] == clips[0][2]:
            j += 1
        kids = wrap([(n, c[1:]) for n, c in items[i:j]], name)
        rule, cmds, _ = clips[0]
        x0, y0, x1, y1 = PD.bounds(list(cmds))
        shape = {"type": "path", "name": name("Clip"), "box": [x0, y0, max(x1 - x0, 1.0), max(y1 - y0, 1.0)],
                 "props": {"d": PD.write(list(cmds)), "filled": True, "fill": "#ffffff", "fillRule": rule}}
        out += [shape, {"type": "group", "name": name("Clipped"), "props": {}, "matte": shape["name"], "layers": kids}]
        i = j
    return out
