"""The gizmo on a bone (SPEC §9), for gizmo_qt.py: turn rings on the bone's head, posed at the playhead, and each drag
step as the calls agents use to pose a chain. No Qt.

A bone is posed only by keys on its Turn (fields.STILL: its head and length are data the chain wrote; its written Turn
is the rest the mesh bends from), so a drag keys: `key.add` at the playhead on each Turn field it moved (a key there, or
the one already there changed). Never the still value, which would move the rest with the pose and bend nothing.
"""
from __future__ import annotations

from rostrum_core.keys import layers
from rostrum3d import aim, skin, through

from . import gizmo as G


def mesh_of(doc, bone_id: str) -> str:
    """The mesh a bone's chain is in."""
    owner = doc.parent_of(bone_id)[0]
    while owner and doc.item(owner).get("type") == "bone":
        owner = doc.parent_of(owner)[0]
    return owner


def frame(doc, bone: dict, values: dict, scene: dict, frame_no: int, t: float):
    """(the parent's world transform the bone's Turn lives in, the head in the world, the bone's own turn (3×3)) at time
    t: the mesh as seen at that frame, then the bones before it posed at t (skin.py's numbers, the ones the core bends
    the mesh with)."""
    mesh = mesh_of(doc, bone["id"])
    world = through.find_item(scene, mesh, frame_no)[0]
    chain = skin.bones_of(doc.item(mesh))
    at = next(i for i, (b, _) in enumerate(chain) if b["id"] == bone["id"])
    parent = chain[at][1]
    carrier = aim.compose(world, skin.transforms(chain, t, layers.stack_of(doc.data))[parent]) if parent >= 0 else world
    return G.item_frame(carrier, values)


def calls(bone_id: str, out: dict, t: float) -> list[dict]:
    """A drag step's calls for the Turn values `out` ({rx: degrees …}) at time t. Each step sends every field the drag has
    moved so far: key.add on a key at the same time changes it, so the gesture's steps stack to where the drag is now."""
    return [{"op": "key.add", "target": [bone_id], "args": {"prop": k, "v": round(float(v), 6), "t": t}} for k, v in out.items()]
