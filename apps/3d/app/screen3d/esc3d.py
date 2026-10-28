"""What Esc means in Rostrum3D, in one written order (the shared key `step_back`). Esc first closes the newest open popup,
menu or sheet wherever the keyboard is (the kit's one Esc: AppShell + OpenPopups; the window's key map waits while one is
open). With none open, Esc takes the FIRST step below that applies, one step per press: never two at once, and never
nothing while something is under way. With none of them, Esc does nothing (there is nothing to step back from).

A typing in place (a 3D text just placed: TypeInPlace.qml) ends on its own Esc before any of this.
"""
from __future__ import annotations

ORDER = (
    ("gizmo", "a gizmo drag: cancel it (the item goes back, no history step)",
     lambda b, v: v is not None and v.gizmo.dragging, lambda b, v: v.gizmo.cancel()),
    ("pose_drag", "a pose drag, a hold or joint being moved: cancel it (the clay goes back, no history step)",
     lambda b, v: v is not None and getattr(v, "pose_tool", None) is not None and v.pose_tool.dragging, lambda b, v: v.pose_tool.cancel()),
    ("stroke", "a clay stroke in progress: cancel it (the clay goes back, no history step)",
     lambda b, v: v is not None and v.clay_tool._phase in ("wait", "sculpt"), lambda b, v: v.clay_tool.cancel()),
    ("draw", "a clay outline being drawn (Draw, Spin): drop it (nothing changes, no history step)",
     lambda b, v: v is not None and v.clay_tool.drawer.drawing, lambda b, v: v.clay_tool.drawer.cancel()),
    ("paint_stroke", "a paint stroke in progress: drop it (nothing painted, no history step; Paint stays on)",
     lambda b, v: v is not None and v.paint.stroking, lambda b, v: v.paint.cancel()),
    ("scrub", "a number being dragged (a field's label, Count, Width): put it back (no history step; the rest of the "
     "drag changes nothing)", lambda b, v: b.scrubbing, lambda b, v: b.cancel_drag()),
    ("render", "a render running: cancel it",
     lambda b, v: b.render.state == "running", lambda b, v: b.render.cancel()),
    ("result", "a render shown over the viewport: put it away",
     lambda b, v: b.render.state in ("done", "failed"), lambda b, v: b.render.dismiss()),
    ("queue_result", "a finished render from the queue shown over the viewport: put it away",
     lambda b, v: b.queue.shown.state == "done", lambda b, v: b.queue.shown.dismiss()),
    ("armed", "a shape waiting for its click: let go of it",
     lambda b, v: b.add.armed != "", lambda b, v: b.add.disarm()),
    ("bones", "bones being placed: cancel them",
     lambda b, v: v is not None and v.bone_tool.on, lambda b, v: v.bone_tool.cancel()),
    ("focus", "picking a camera's focus: stop",
     lambda b, v: v is not None and bool(v.focus.camera), lambda b, v: v.focus.stop()),
    ("surface", "picking the surface to scatter copies over: stop",
     lambda b, v: v is not None and v.copies.wants_click(), lambda b, v: v.copies.stop()),
    ("link", "picking what a light lights: finish",
     lambda b, v: v is not None and bool(v.place.mode), lambda b, v: v.place.stop()),
    ("knife", "the Knife's line: drop it",
     lambda b, v: v is not None and v.mesh_edit.knifing, lambda b, v: v.mesh_edit.escape()),
    ("mesh", "Edit mesh: leave it",
     lambda b, v: v is not None and v.mesh_edit.on, lambda b, v: v.mesh_edit.leave()),
    ("paint", "Paint: leave it",
     lambda b, v: v is not None and v.paint.on, lambda b, v: v.paint.leave()),
    ("clay", "the Clay tool: back to Select",
     lambda b, v: v is not None and v.clay_tool.on, lambda b, v: v.clay_tool.leave()),
    ("pose", "the Pose tool: back to Select",
     lambda b, v: v is not None and getattr(v, "pose_tool", None) is not None and v.pose_tool.on, lambda b, v: v.pose_tool.leave()),
    ("blocks", "a material's blocks in the bottom panel: back to the timeline",
     lambda b, v: getattr(b, "_blocks", None) is not None and b._blocks.open, lambda b, v: b._blocks.close()),
    ("stretch", "an animation picked on the timeline: back to its item",
     lambda b, v: b._stretch.shown, lambda b, v: b._stretch.clear()),
    ("keys", "several keys picked: let go of them",
     lambda b, v: b._keys.count > 1, lambda b, v: b._keys.clear()),
    ("selection", "a selection: let go of it (the Scene panel shows)",
     lambda b, v: b.selected != "", lambda b, v: b.select("")),
)


def step(bridge) -> str:
    """Take the first step that applies; its name ("" when nothing applied)."""
    v = getattr(bridge, "viewport", None)
    for name, _words, applies, do in ORDER:
        if applies(bridge, v):
            do(bridge, v)
            return name
    return ""
