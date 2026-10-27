"""Clay steps on the agent's pictures (SPEC § 6): look_at's `step` and `joint` for a clay hit, and look_frame's
`highlight="steps:<name or id>,…"` outlines.

Highlight, without a pick per pixel (a pick is one Storm pass, ~6 ms): the clay's rest grid (clay_grid) gives its
surface cells; each is given to its step (step_find); they go through the clay's world transform at the frame and the
shot camera onto the picture, nearest in front (a small depth buffer); the chosen steps' pixels are closed into a
region, tinted and outlined 2 px. A few picks inside the region then say if another item hides part of it. A posed
clay's points are posed first (`posed`: the core's skin weights, blended linearly).
"""
from __future__ import annotations

import functools

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from rostrum_core.errors import RostrumError, codes

from rostrum3d import aim, clay_dabs, ops_pose, pose_joints as PJ, step_find as SF
from rostrum3d.resolve import Frames

PREFIX = "steps:"
CELLS = 96
COLOURS = [(255, 214, 0), (0, 229, 255), (255, 64, 160), (120, 255, 90), (255, 140, 0)]
CHECKS = 16                     # picks (~6 ms each) that test whether another item hides the outlined region

HIGHLIGHT = {"highlight": {"type": "string", "description": 'Outline what clay steps made: "steps:arm" or "steps:arm,foot" (step names or '
                                                           'ids, as look_at\'s `step` gives them). Each in its own colour, tinted, 2 px edge.'}}


def _dabs(folder):
    """A stroke's dabs file, read once (no project folder: none)."""
    return functools.lru_cache(None)(lambda ref: clay_dabs.read(folder, ref) if folder else [])


def about(doc, folder, hit: dict) -> dict:
    """{step, joint} for a pick on a clay (in its rest space when posed); {} for anything else."""
    if not hit.get("hit") or not hit.get("local") or not doc.has(hit["item"]):
        return {}
    clay = doc.item(hit["item"])
    if clay.get("type") != "clay":
        return {}
    spot = hit.get("rest") or hit["local"]
    out = {"step": SF.find(clay.get("steps", []), spot, _dabs(folder)),
           "joint": SF.nearest_joint(PJ.joints_of(clay), spot) if clay.get("bones") else None}
    return {k: v for k, v in out.items() if v}


def words(extra: dict, length) -> str:
    s, j = extra.get("step"), extra.get("joint")
    return ((f', made by step {s["id"]} ({s["label"]})' if s else "")
            + (f', nearest joint {j["joint"]} ({length(j["distance"])} off)' if j else ""))


def chosen(ctx, doc, highlight: str) -> dict:
    """{clay id: [step ids]} the highlight names; loud for anything unknown."""
    if not highlight.startswith(PREFIX):
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f'highlight "{highlight}"', 'must start with "steps:"', hint='e.g. "steps:arm,foot"')
    names = [n.strip() for n in highlight[len(PREFIX):].split(",") if n.strip()]
    clays = [i for i in doc.items() if i.get("type") == "clay"]
    out, found = {}, set()
    for c in clays:
        ids, _ = SF.match(c.get("steps", []), names)
        if ids:
            out[c["id"]] = [s["id"] for s in c["steps"] if s["id"] in ids]
            found |= {n for n in names if any(n in (s["id"], s.get("name")) for s in c["steps"])}
    missing = [n for n in names if n not in found]
    if missing or not names:
        steps = {c["id"]: [s.get("name") or s["id"] for s in c.get("steps", [])] for c in clays}
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f'highlight step{"s" if len(missing) > 1 else ""} {", ".join(missing) or "(none)"}',
                           "is not a step of any clay here" if clays else "names a step, and there is no clay here",
                           [f'{c}: {", ".join(n) or "no steps"}' for c, n in steps.items()])
    return out


def _surface(doc, clay_id):
    grid = ops_pose._GRID(doc.data, clay_id, CELLS)
    occ = PJ.occupancy(grid)
    inner = occ.copy()
    for ax in range(3):
        for s in (1, -1):
            inner &= np.roll(occ, s, axis=ax)
    idx = np.argwhere(occ & ~inner)
    return np.asarray(grid["origin"]) + (idx + 0.5) * grid["cell"], float(grid["cell"])


def _project(doc, info, clay_id, frame, pts, w, h):
    """Picture px x, y and depth (m) of clay-space points at `frame` through the shot camera."""
    fr = Frames(doc.data, range(frame, frame + 1), info["fps"])
    world, cam, cv = fr.world(clay_id, frame), fr.world(info["camera"], frame), fr.values(info["camera"], frame)
    to_cam = aim.invert(cam)
    m = np.asarray(aim._mul(to_cam[0], world[0]))
    t = np.asarray(aim.point(to_cam, world[1]))
    p = pts @ m.T + t
    depth = -p[:, 2]
    tan_w = cv["sensorWidth"] / (2 * cv["focalLength"])
    tan_h = tan_w * h / w
    with np.errstate(divide="ignore", invalid="ignore"):
        x = (p[:, 0] / depth / tan_w + 1) / 2 * w
        y = (1 - p[:, 1] / depth / tan_h) / 2 * h
    scale = float(np.abs(np.linalg.det(m))) ** (1 / 3)
    return x, y, depth, scale / (2 * tan_w) * w                     # px per metre at depth 1


def masks(doc, folder, info, frame, w, h, wanted: dict) -> dict:
    """{(clay, step id): bool mask [h, w]}: where each wanted step's surface shows, nearest in front."""
    out = {}
    for clay_id, ids in wanted.items():
        clay = doc.item(clay_id)
        pts, cell = _surface(doc, clay_id)
        steps = SF.live(clay.get("steps", []))
        own, _ = SF.owners(steps, pts, _dabs(folder))
        if clay.get("bones"):
            pts = posed(clay, pts, frame / info["fps"])
        x, y, depth, k = _project(doc, info, clay_id, frame, pts, w, h)
        ok = (depth > 1e-4) & (x > -8) & (y > -8) & (x < w + 8) & (y < h + 8)
        r = np.maximum(1, np.rint(cell * k / np.where(ok, depth, 1) * 0.5)).astype(int)     # half a cell: no spill past the edge
        order = np.argsort(-depth[ok])                               # far first: the nearest is written last
        xs, ys, rs, os_ = x[ok][order], y[ok][order], r[ok][order], own[ok][order]
        buf = np.full((h, w), -2, int)
        for dy in range(-rs.max(), rs.max() + 1):
            for dx in range(-rs.max(), rs.max() + 1):
                m = (np.abs(dx) <= rs) & (np.abs(dy) <= rs)
                px, py = (xs[m] + dx).astype(int), (ys[m] + dy).astype(int)
                inb = (px >= 0) & (py >= 0) & (px < w) & (py < h)
                buf[py[inb], px[inb]] = os_[m][inb]
        for sid in ids:
            i = next((n for n, s in enumerate(steps) if s["id"] == sid), None)
            if i is not None:
                out[(clay_id, sid)] = buf == i
    return out


def posed(clay, pts, t: float):
    """Rest points of a clay with bones, posed at t seconds: the core's clay skin rule (ENGINE_CONTRACT, Clay with
    bones: the 4 nearest bones by 1 / distance⁴ to their rest segments, a point behind a bone's head 3 × farther,
    influences under 2 % dropped), blended linearly (the core blends clay as dual quaternions: close enough for an
    outline)."""
    from rostrum3d import pose_ik, skin
    rig = pose_ik.Rig(clay, t)
    d = []
    for m, b in zip(rig.rest, rig.bones):
        seg = skin.segment(m, b)
        head, tail = np.asarray(seg[:3]), np.asarray(seg[3:])
        axis = (tail - head) / max(float(np.linalg.norm(tail - head)), 1e-9)
        behind = np.maximum(0.0, -(pts - head) @ axis)
        d.append(SF._seg(pts, head, tail) + 3.0 * behind)
    d = np.maximum(np.stack(d, axis=1), 1e-6)                        # (N, bones)
    wt = 1.0 / d ** 4
    if wt.shape[1] > 4:
        wt[d > np.sort(d, axis=1)[:, 3:4]] = 0.0
    wt /= wt.sum(axis=1, keepdims=True)
    wt[wt < 0.02] = 0.0
    wt /= wt.sum(axis=1, keepdims=True)
    out = np.zeros_like(pts)
    for n, mv in enumerate(rig.pose()):
        lin, tr = np.asarray(mv[:9]).reshape(3, 3), np.asarray(mv[9:])
        out += wt[:, n:n + 1] * (pts @ lin.T + tr)
    return out


def overlay(png, regions: dict, names: dict) -> list[dict]:
    """Tint and outline each region on the PNG in place; [{clay, step, name, colour, pixels, box}]."""
    im = Image.open(png).convert("RGBA")
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    out = []
    for n, (key, mask) in enumerate(regions.items()):
        col = COLOURS[n % len(COLOURS)]
        m = Image.fromarray((mask * 255).astype(np.uint8), "L").filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))
        edge = Image.fromarray(np.asarray(m) & ~np.asarray(m.filter(ImageFilter.MinFilter(5))))
        layer.paste((*col, 60), (0, 0, *im.size), m)
        layer.paste((*col, 255), (0, 0, *im.size), edge)
        a = np.asarray(m) > 0
        ys, xs = np.nonzero(a)
        box = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if xs.size else None
        if box:
            ImageDraw.Draw(layer).text((box[0], max(0, box[1] - 14)), names[key], fill=(*col, 255))
        out.append({"clay": key[0], "step": key[1], "name": names[key], "colour": "#%02x%02x%02x" % col,
                    "pixels": int(a.sum()), "box": box, "mask": a})
    Image.alpha_composite(im, layer).convert("RGB").save(png)
    return out


def hidden_by(pick, region: dict, clay: str) -> list[str]:
    """Items other than the clay that a few picks inside the region hit (what hides part of it)."""
    core = Image.fromarray((region["mask"] * 255).astype(np.uint8), "L").filter(ImageFilter.MinFilter(7))
    ys, xs = np.nonzero(np.asarray(core))                         # well inside: not its edge
    if not xs.size:
        return []
    tries, others = np.linspace(0, xs.size - 1, min(CHECKS, xs.size)).astype(int), {}
    for i in tries:
        r = pick(float(xs[i]), float(ys[i]))
        if r.get("hit") and r.get("item") != clay:
            others[r["item"]] = others.get(r["item"], 0) + 1
    return sorted(k for k, n in others.items() if n >= max(2, len(tries) // 5))       # a stray edge pick isn't hiding
