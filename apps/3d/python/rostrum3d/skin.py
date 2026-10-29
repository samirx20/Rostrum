"""A mesh's bone chain as numbers (SPEC §9, simple bone chains): each bone's place in the mesh's own space, at rest
and at any time, and the compiler's `skin` for the core (which works out the weights itself, from each point's
distance to the bones at rest, and bends the mesh with the pose).

Convention (one for the whole app): a bone's transform is aim.local's with no scale (turned rx, then ry, then rz,
degrees, then moved to its head x y z), in its parent's space: the mesh's own space for the first bone of a chain,
else the bone before it. A bone runs from its head along its own +Y for `length`: its tail is (0, length, 0) in its
own space, which is where the next bone's head sits. Rest = the bones' written values (no keys); now = their Turn
keys' values at that time (only Turn is keyed: fields.STILL).

The core's contract (`skin` on a mesh node, all in the MESH's own space, one pose entry per frame of the shot):
    "skin": {"rest": [[hx, hy, hz, tx, ty, tz], ...one per bone, parents first],
             "pose": [[[m00, m01, m02, m10, m11, m12, m20, m21, m22, x, y, z], ...one per bone], ...one per frame]}
p_now = M·p_rest + (x, y, z), M row-major as listed: the bone's transform now times the inverse of its rest one.
"""
from __future__ import annotations

from rostrum_core.keys import keys_of, layers, track_value

from . import aim

TURN = ("rx", "ry", "rz")
HEAD = ("x", "y", "z")


def bones_of(mesh: dict) -> list[tuple[dict, int]]:
    """Every bone in the mesh's chains, each after its parent: [(bone, its parent's index here, or -1)]."""
    out, stack = [], [(b, -1) for b in reversed(mesh.get("bones", []))]
    while stack:
        bone, parent = stack.pop()
        out.append((bone, parent))
        stack += [(c, len(out) - 1) for c in reversed(bone.get("bones", []))]
    return out


def _local(bone: dict, t: float | None, stack: list[dict] = ()):
    v = {k: float(bone.get(k, 0.0)) for k in (*HEAD, *TURN)}
    for k in TURN if t is not None else ():
        if keys := keys_of(bone, k):
            v[k] = float(track_value(keys, t))
        v[k] = float(layers.value(bone, k, t, stack, v[k]))          # its animation layers (none: unchanged)
    return aim.local({**v, "sx": 1.0, "sy": 1.0, "sz": 1.0})


def transforms(chain: list[tuple[dict, int]], t: float | None = None, stack: list[dict] = ()) -> list:
    """Each bone's transform in the mesh's own space: at rest (t None) or at time t (seconds), with the document's
    animation layers (`stack`, layers.stack_of) laid over."""
    out = []
    for bone, parent in chain:
        own = _local(bone, t, stack)
        out.append(aim.compose(out[parent], own) if parent >= 0 else own)
    return out


def segment(m, bone: dict) -> list[float]:
    """[head xyz, tail xyz] of a bone whose transform is m."""
    return [*aim.point(m, [0.0, 0.0, 0.0]), *aim.point(m, [0.0, float(bone.get("length", 0.0)), 0.0])]


def _deform(now, rest) -> list[float]:
    lin, t = aim.compose(now, aim.invert(rest))
    return [round(x, 6) for x in (*lin[0], *lin[1], *lin[2], *t)]


def skin(mesh: dict, times: list[float], stack: list[dict] = ()) -> dict | None:
    """The core's `skin` for a mesh at these times (seconds, one per frame), or None: no bones, or Bend with bones off."""
    chain = bones_of(mesh)
    if not chain or not mesh.get("skinned", True):
        return None
    rest = transforms(chain)
    segs = [[round(x, 6) for x in segment(m, b)] for m, (b, _) in zip(rest, chain)]
    out = {"rest": segs, "pose": [[_deform(n, r) for n, r in zip(transforms(chain, t, stack), rest)] for t in times]}
    if mesh.get("jointParts"):                                 # a clay's pieces (skin_parts.py): each bends with its own
        from . import skin_parts
        if parts := skin_parts.for_core(mesh["jointParts"], chain, segs):
            out["parts"] = parts
    return out


def frame_times(fr, id_: str) -> list[float]:
    """The time each of the shot's frames shows for this mesh's bones: its Timing (On 2s / 3s) holds them too."""
    n, first = fr.step(id_), fr.frames[0]
    return [(first + (f - first) // n * n) / fr.fps for f in fr.frames]
