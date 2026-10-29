"""`clay.clean_mesh` (SPEC PR4): the clay's surface rebuilt as an even mesh of four-sided faces (remesh.py, Instant
Meshes) and added as a new editable mesh beside the clay: same place, turn, size and material, named "<clay> mesh".
The clay is hidden (Visible off), not removed, so it can still be sculpted and made into a mesh again. One undo step.

The rebuild itself is analysed once and kept in the shared cache. The window runs it first as a background job (with
progress and Cancel) and then calls this operation, which finds it there; an agent or a script calling it directly
waits for it here (a few seconds for a typical clay).
"""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.tree import index

from . import build, remesh
from .kind import REGISTRY as R
from .ops_mesh import TRANSFORM_KEYS

DEFAULT_FACES = 4000


@R.operation("clay.clean_mesh", "Make a clean mesh: the clay's surface as drawn now (its layers and pose included) "
             "rebuilt as an even mesh of four-sided faces that follow its shape (Instant Meshes), for export, rigging "
             "or editing as a mesh. Added as a new mesh beside the clay with its place and material; the clay is "
             "hidden, not removed. `faces`: about how many faces (default 4000; more keeps finer detail). The rebuild "
             "is kept, so the same clay and count again is instant. One undo step. Paint on the clay is not carried "
             "over.", target="clay", label="Make a clean mesh", importance="secondary",
             params=[Param.number("faces", label="Faces", min=remesh.FACES[0], max=remesh.FACES[1], integer=True,
                                  step=500, default=DEFAULT_FACES,
                                  help="About how many four-sided faces the clean mesh has"),
                     Param.text("name", label="Name", help='The new mesh\'s name (default "<clay> mesh")')])
def clay_clean_mesh(ctx, targets, args):
    faces = int(args.get("faces", DEFAULT_FACES))
    made = []
    for t in targets:
        clay = ctx.item(t)
        try:
            raw = remesh.surface(ctx.doc, t)
            folder = remesh.compute(raw, faces, remesh.key_of(raw, faces))
        except Exception as e:  # noqa: BLE001  the engine's or the rebuild's failure is this operation's, named
            ctx.fail(codes.BAD_ARGUMENT, f'target "{t}"', f"could not be made into a clean mesh: {e}",
                     hint="Check the clay shows in look_frame; sculpt something first if it is empty.")
        points, polys = remesh.read(folder)
        loc = index(ctx.doc, ctx.kind.lists)[t]
        mesh = build.make("mesh", ctx.new_id("mesh"),
                          {"name": args.get("name") if len(targets) == 1 and args.get("name") else
                           f'{clay.get("name") or t} mesh', "material": clay.get("material", ""), "shape": "poly",
                           "points": points, "faceCounts": [len(f) for f in polys],
                           "faceIndices": [i for f in polys for i in f]}, ctx.where)
        mesh.update({k: clay[k] for k in TRANSFORM_KEYS if k in clay})
        ctx.insert(loc.parent, loc.key, mesh, loc.index + 1)
        ctx.set(t, "visible", False)
        made.append({"clay": t, "mesh": mesh["id"], "faces": len(polys), "points": len(points)})
    return {"made": made}
