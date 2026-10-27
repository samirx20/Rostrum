"""Mirrored copies (3D simplicity SPEC §1 at 3:40, §9 row 4): a mesh put on a mirrored clay gets a copy on the other
side of the clay's mirror (its own X = 0 plane) that follows it. The copy is a mesh with `mirror` (the original's id)
and `mirrorOn` (the clay's id). Everything it shows is worked out from the original, per frame (resolve.py): its
shape, material, keys and visibility are the original's, its place is the original's reflected through the plane.
The engine never knows: it gets two plain meshes. Its own stored fields are not used.

Edits sent to the copy go to the original (`redirect`, used by every `mesh.set`): a size or a colour as it is, a move
reflected back, so moving the copy left moves the original right. The material and paint operations aimed at a copy
act on its original (`REDIRECTED`, wrapped once in kind.py). Anything else that would change only the copy (a key,
an aim, a bone, an edit of its points) is refused by the document check (`stray`), naming the original. Removing the original or the clay removes the copy
(ops_mirror.py). Plain maths, no Qt.
"""
from __future__ import annotations

from . import aim, follow

FIELDS = ("mirror", "mirrorOn")           # the link: the copy's own, never sent to the engine
OWN = {"id", "name", *FIELDS}             # what the copy keeps of its own; everything else is the original's
FLIP = ([[-1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], [0.0, 0.0, 0.0])
SYMMETRIC = {"box", "sphere", "cylinder", "cone", "capsule", "plane", "disc", "torus"}   # the same seen from either side
TRS = follow.TRS
SUFFIX = " (mirrored)"                    # the copy's name in the scene list: "eye (mirrored)"


def reflection(clay_world):
    """The world transform that mirrors through the clay's own X = 0 plane (its own inverse)."""
    return aim.compose(clay_world, aim.compose(FLIP, aim.invert(clay_world)))


def mirrored(world, clay_world, shape: str):
    """The copy's world transform from the original's. A shape that is the same from either side (a ball, a box …) is
    turned back inside, so the copy is a plain turned shape with no mirror in its scale; others (text, an editable
    mesh) keep the mirror (a negative X scale), so a word reads backwards on the other side, as in a mirror."""
    m = aim.compose(reflection(clay_world), world)
    return aim.compose(m, FLIP) if shape in SYMMETRIC else m


def targets(items: dict, id_: str) -> tuple[str, str]:
    """(original, clay) of a copy, checked: loud when either is missing or of the wrong kind."""
    item = items[id_]
    orig, clay = item.get("mirror") or "", item.get("mirrorOn") or ""
    if orig not in items or items[orig].get("type") != "mesh":
        raise ValueError(f'{id_}: a mirrored copy of "{orig}", which is not a mesh')
    if items[orig].get("mirror"):
        raise ValueError(f'{id_}: a mirrored copy of "{orig}", which is a mirrored copy itself')
    if clay not in items or items[clay].get("type") != "clay":
        raise ValueError(f'{id_}: mirrored across "{clay}", which is not a clay')
    return orig, clay


def _parent(fr, id_: str, f: int):
    parent = fr.parent[id_]
    return fr.world(parent, f) if parent else aim.IDENTITY


def values(fr, id_: str, f: int) -> dict:
    """The copy's values at frame f (resolve.Frames): the original's, placed through the mirror, in the copy's parent's
    space; nothing left to resolve (no aim, follow, stick or pivot of its own)."""
    item = fr.items[id_]
    orig, clay = targets(fr.items, id_)
    v = dict(fr.values(orig, f))
    world = mirrored(fr.world(orig, f), fr.world(clay, f), v["shape"])
    v.update(follow.decompose(aim.compose(aim.invert(_parent(fr, id_, f)), world)))
    v.update(px=0.0, py=0.0, pz=0.0, aim="none", follow="", stick="", **{k: item[k] for k in FIELDS})
    return v


def stored(orig: dict) -> dict:
    """What a new copy stores of its own: the original's shape, so the edits that only apply to a shape (a ball's
    radius) are accepted when sent to the copy (and passed on). An editable mesh's points stay the original's alone."""
    return {"shape": orig["shape"]} if orig.get("shape", "box") != "poly" else {}


REDIRECTED = {"material.assign", "material.split", "material.from", "paint.add", "paintmask.add"}   # act on the original
LINKED = {*OWN, "type", "shape"}          # a copy's stored fields the check leaves alone (`stored`)
LOOKS = ("keys", "bones", "paints", "paintmasks")      # lists that would be the copy's own: always empty


def originals(items: dict, ids) -> list:
    """`ids` with every mirrored copy replaced by its original, each once (items: id -> item)."""
    return list(dict.fromkeys((items[i].get("mirror") or i) if i in items else i for i in ids))


def redirected(fn):
    """An operation's function that acts on the originals of the copies it is aimed at (targets, and a `to` list)."""
    def on_originals(ctx, targets, args):
        items = {i: ctx.item(i) for i in [*(targets or []), *(args.get("to") or [])]}
        if args.get("to"):
            args = {**args, "to": originals(items, args["to"])}
        return fn(ctx, originals(items, targets) if targets else targets, args)
    return on_originals


def stray(item: dict, defaults: dict) -> list[str]:
    """What was set on a copy that only its original holds: its fields changed from a new copy's, or keys, bones, paint
    of its own. [] for a copy as mesh.mirror makes it (and for any other item)."""
    if not item.get("mirror"):
        return []
    return ([k for k, v in item.items() if k not in LINKED and k not in LOOKS and k in defaults and v != defaults[k]]
            + [k for k in LOOKS if item.get(k)])


def copies_of(items, ids) -> list[str]:
    """Every mirrored copy whose original or clay is one of `ids` (items: an iterable of item dicts)."""
    ids = set(ids)
    return [i["id"] for i in items if i.get("type") == "mesh" and (i.get("mirror") in ids or i.get("mirrorOn") in ids)]


def redirect(data: dict, id_: str, args: dict) -> list[tuple[str, str, object]]:
    """(target, field, value) writes for a `mesh.set` of `args` on `id_` (data: the document): on a copy, its name
    stays its own and every other field goes to the original; a move, turn or scale is reflected back into the
    original's own space. Raises ValueError (said plainly) when the original's place is worked out (aim, follow,
    stick, pivot, keys on its move)."""
    from .resolve import Frames
    fr = Frames(data, range(0, 1), 1.0)
    if not fr.items[id_].get("mirror"):
        return [(id_, k, v) for k, v in args.items()]
    orig, clay = targets(fr.items, id_)
    out = [(id_ if k in OWN else orig, k, v) for k, v in args.items() if k not in TRS]
    moved = {k: args[k] for k in TRS if k in args}
    if moved:
        out += [(orig, k, v) for k, v in _moved_back(fr, id_, orig, clay, moved).items()]
    return out


def _moved_back(fr, id_, orig, clay, moved: dict) -> dict:
    """The original's x … sz that put the copy where `moved` says (time 0)."""
    o = fr.items[orig]
    worked = [w for w, on in (("its aim", o.get("aim", "none") != "none"), ("Follow", o.get("follow")),
                              ("Stick to", o.get("stick")), ("a pivot", any(o.get(p) for p in ("px", "py", "pz"))),
                              ("keys", any(k.get("prop") in TRS for k in o.get("keys", []))))
              if on]
    if worked:
        raise ValueError(f'{id_} is a mirrored copy of {orig}, whose place is worked out ({", ".join(worked)}); '
                         f"move {orig} instead (its copy follows)")
    want = {**fr.values(id_, 0), **moved}
    world = aim.compose(_parent(fr, id_, 0), aim.local(want))
    back = mirrored(world, fr.world(clay, 0), o.get("shape", "box"))      # a mirror twice is no mirror
    new = follow.decompose(aim.compose(aim.invert(_parent(fr, orig, 0)), back))
    return {k: round(v, 6) for k, v in new.items() if abs(v - o.get(k, 1.0 if k[0] == "s" else 0.0)) > 1e-7}
