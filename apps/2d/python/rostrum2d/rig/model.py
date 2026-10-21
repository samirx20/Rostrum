"""What a rig must satisfy and where its parts sit at rest (RIG.md). Checked after every call, so a bad rig is
refused with the item named; never left for the engine to find at load."""
from __future__ import annotations

import math

from rostrum_core.errors import did_you_mean


def tip(bone: dict) -> tuple[float, float]:
    """Where a bone ends at rest (rig px): `length` along `angle` from its pivot."""
    a = math.radians(bone["angle"])
    return bone["x"] + bone["length"] * math.cos(a), bone["y"] + bone["length"] * math.sin(a)


def start_bone(bones: list, values: dict) -> dict:
    """A new bone's fields: a child starts where its parent ends, pointing the same way."""
    parent = next((b for b in bones if b["id"] == values.get("parent")), None)
    out = dict(values)
    if parent:
        out.setdefault("x", tip(parent)[0])
        out.setdefault("y", tip(parent)[1])
        out.setdefault("angle", parent["angle"])
    return out


def start_ik(bones: list, values: dict) -> dict:
    """A new chain's fields: the target starts where the lower bone's tip already is."""
    lower = next((b for b in bones if b["id"] == values.get("bone")), None)
    out = dict(values)
    if lower:
        out.setdefault("targetX", tip(lower)[0])
        out.setdefault("targetY", tip(lower)[1])
    return out


def _pick(kind, id_, what, ids_, problems, owner):
    """True when `id_` is among `ids_`; otherwise the problem, naming the owner and the nearest id."""
    if id_ in ids_:
        return True
    hint = did_you_mean(id_, list(ids_)) if id_ else ""
    problems.append(f'{owner}: {what} "{id_}" is not a {kind} of this rig' + (f" {hint}" if hint else
                    f" (it has: {', '.join(ids_) or 'none yet'})"))
    return False


def problems_of(rig: dict) -> list[str]:
    """Bones: parent exists, no cycle. Iks: the lower bone exists and has a parent (the upper bone). Binds: the
    layer is one of the rig's own layers (one bind each), bone and bone2 are bones, bone2 hangs from bone."""
    out, bones = [], {b["id"]: b for b in rig.get("bones", [])}
    layers = [l["id"] for l in rig.get("layers", [])]
    for b in bones.values():
        p = b["parent"]
        if p and not _pick("bone", p, "parent", list(bones), out, f'bone {b["id"]}'):
            continue
        seen, cur = {b["id"]}, p
        while cur:
            if cur in seen:
                out.append(f'bone {b["id"]}: its parents go round in a circle (through {cur})')
                break
            seen.add(cur)
            cur = bones[cur]["parent"] if cur in bones else ""
    for k in rig.get("iks", []):
        who = f'ik {k["id"]}'
        if _pick("bone", k["bone"], "bone", list(bones), out, who) and not bones[k["bone"]]["parent"]:
            out.append(f'{who}: bone "{k["bone"]}" has no parent; a chain needs an upper bone above it')
        elif k["bone"] in bones and int(k.get("chain", 2)) > 2:
            have, cur = 0, k["bone"]
            while cur in bones and have <= len(bones):
                have, cur = have + 1, bones[cur]["parent"]
            if have < int(k["chain"]):
                out.append(f'{who}: a chain of {int(k["chain"])} bones needs {int(k["chain"])} bones from "{k["bone"]}" '
                           f"up; there are {have}")
    bound = {}
    for b in rig.get("binds", []):
        who = f'bind {b["id"]}'
        if _pick("layer", b["layer"], "layer", layers, out, who):
            if b["layer"] in bound:
                out.append(f'{who}: layer "{b["layer"]}" is already bound by {bound[b["layer"]]} (one bind per layer)')
            bound[b["layer"]] = b["id"]
        ok = _pick("bone", b["bone"], "bone", list(bones), out, who)
        if b["bone2"] and _pick("bone", b["bone2"], "bone2", list(bones), out, who) and ok \
                and bones[b["bone2"]]["parent"] != b["bone"]:
            out.append(f'{who}: bone2 "{b["bone2"]}" must be a child of bone "{b["bone"]}" to bend across its joint')
    return out


def binds_to_drop(data: dict, layer_ids: set) -> list[str]:
    """Ids of the binds of these layers (a layer leaving its rig or deleted takes its bind with it)."""
    found, stack = [], [data]
    while stack:
        item = stack.pop()
        found += [b["id"] for b in item.get("binds", []) if b["layer"] in layer_ids]
        for key in ("comps", "layers"):
            stack += item.get(key, [])
    return found
