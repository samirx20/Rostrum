"""Rostrum3D's action list, as plain data read into the kit's one list (rostrum_gui/actions.py): what the selection
allows, at the top of the settings panel (SPEC §3.3, "Combine: Union · Subtract · Intersect"). Only what applies is
offered (rule of individuality). Each action is one change made of operations an agent calls too (`combine.make`).
Today: Combine, on two or more solids (meshes or combines) in the same list; the first picked is the base, every
later one a cutter or partner. And "Bevel too big · use 1.84 mm (the largest that fits)": when the engine refused an outline's bevel (text,
logo, drawing; SPEC §4.4), the largest bevel that fits, one click away (`mesh.set bevel`). And Send to 2D on a shot
(send_qt.py; agents: render_send_shot). And the edit block every app has (Duplicate, Delete, Copy / Paste material),
Make copies / Scatter / Change near (copies_actions.py), what a light, a mouth group or empty space offers (Look through, Pick what it lights, Lip sync…, New shot from this
view, Back to the shot's view). Right-click is this list (the kit's ActionMenu fed by the hub's `menu()`), so it never
holds an action the panel, Ctrl+K or a key wouldn't run; eight entries at most (six, Make copies ›, Simulate ›). No Qt.
"""
from __future__ import annotations

import re

from rostrum3d import fields as F, mouths
from rostrum3d.clay_fields import SOURCES
from rostrum3d.kind import KIND
from rostrum_core import ids
from rostrum_core.tree import index
from rostrum_gui.actions import Action, ActionList

from .copies_actions import ACTIONS as COPIES_ACTIONS
from .keys3d import KEYS3D
from .shots import FRAMED, framed
from .sim_actions import ACTIONS as SIM_ACTIONS

WORDS = {"union": "Union", "subtract": "Subtract", "intersect": "Intersect"}


class Facts:
    """The selection as the kit's guard reads it: `ids` in pick order (the base first), `items`, the document and the
    named truths an action's `when` reads."""

    def __init__(self, doc, selection: list[str], fits: dict | None = None, screen: dict | None = None):
        """`screen`: what the screen knows and the document doesn't (screen state, never saved): {copied: the material
        Copy material took, shot_id: the shot shown, can_shot: a shot can be made, mode: the viewport's camera
        ("shot" | "free" | "light"), has_shot: the viewport has a shot camera, camera: the shown shot's camera}."""
        self.doc, self.ids = doc, [i for i in selection if doc.has(i)]
        self.fits = fits or {}          # {item id: the largest bevel that fits, metres} from the engine's last refusal
        self.screen = screen or {}
        self.items = [doc.item(i) for i in self.ids]
        where = {doc.parent_of(i)[:2] for i in self.ids}
        self.facts = {"same_list": len(where) == 1, "solids": all(it["type"] in F.SOLIDS for it in self.items)}


# The core's refusal (extrude.cpp): "<id>.bevel: 0.01 m is too big for … Accepted: at most 0.00184 m for this outline"
# or "… Accepted: 0 (this outline is too thin for a bevel)".
_TOO_BIG = re.compile(r"([\w.-]+)\.bevel: [^:]*? m is too big for .*?Accepted: (?:at most )?([0-9.eE+-]+)")


def bevel_fits(line: str) -> dict:
    """{item id: largest bevel that fits (m)} read from an engine failure line; {} when it isn't a bevel refusal."""
    m = _TOO_BIG.search(line or "")
    return {m.group(1): float(m.group(2))} if m else {}


def _fit_word(f) -> str:
    """The same offer as the bevel row's button (the row's note says why)."""
    v = f.fits[f.ids[0]]
    return f"Use {v * 1000:.2f} mm" if v > 0 else "Use none"


def fit_note(fits: dict, item_id: str) -> str:
    """The line under the Bevel row when the engine refused its size ("" = nothing to say)."""
    return "The bevel is too big for this outline: use the largest that fits." if item_id in fits else ""


def _fit_label(f) -> str:
    v = f.fits.get(f.ids[0], 0) if f.ids else 0       # asked for every action's name (why_not): absent when no bevel was refused
    return f"Bevel too big · use {v * 1000:.2f} mm (the largest that fits)" if v > 0 else "Bevel too big · use none"


def new_id(doc) -> str:
    return ids.counted(index(doc.data, KIND.lists), "combine")


def _make(op):
    return lambda f: [{"op": "combine.make", "target": list(f.ids), "args": {"op": op, "id": new_id(f.doc)}}]


ACTIONS = [
    Action(f"combine:{op}", WORDS[op], kinds=F.SOLIDS, min_targets=2, importance="primary", rank=5, group="shape",
           bar="Combine", when={"fact": "same_list"}, calls=_make(op), icon=op,
           why=f"{WORDS[op]} needs two or more solids (shapes or combines) in the same group, picked base first.")
    for op in F.COMBINE_OPS
]
ACTIONS.append(Action(
    "bevel:fit", _fit_label, kinds=("mesh",), max_targets=1, importance="primary", rank=1, group="shape",
    row="bevel", row_label=_fit_word,
    valid=lambda f: f.ids[0] in f.fits,
    calls=lambda f: [{"op": "mesh.set", "target": [f.ids[0]], "args": {"bevel": round(f.fits[f.ids[0]], 6)}}],
    why="Offered when the engine refused a text's or logo's bevel as too big for its outline."))
ACTIONS.append(Action(
    "clay:from", "Turn into clay", kinds=SOURCES, importance="secondary", rank=9, group="shape",
    valid=lambda f: not any(it.get("backdrop") for it in f.items), do="clay-from",
    why="Turn into clay works on shapes, combines, imports and their parts (not the floor a scene stands on): a clay "
        "copy to sculpt, the original hidden."))
ACTIONS.append(Action(
    "mesh:edit", "Edit mesh", kinds=F.SOLIDS, max_targets=1, importance="primary", rank=8, group="shape", do="edit-mesh",
    job="go_in", icon="", why="Edit mesh works on one shape or combine (Enter): its points, edges and faces."))
# A camera (SPEC §8): real lenses one click away on the Focal length row ("Lenses ▾") (any other focal length is typed in its field); with
# depth of field on, focus picked by clicking in the viewport (focus_pick.py: screen state until the click's one edit).
LENSES = (24, 35, 50, 85, 105, 135)
# Both sit on their settings rows (Action.row): the lenses on Focal length, Focus on an item on the Focus on row.
_ONE_CAMERA = dict(kinds=("camera",), max_targets=1, importance="primary", group="camera")
ACTIONS += [Action(f"lens:{mm}", f"{mm} mm", rank=2 + i, bar="Lenses", row="focalLength", **_ONE_CAMERA,
                   calls=lambda f, mm=mm: [{"op": "camera.set", "target": [f.ids[0]], "args": {"focalLength": float(mm)}}],
                   why="A lens is offered with one camera selected (any other focal length: type it).")
            for i, mm in enumerate(LENSES)]
_DOF = dict(valid=lambda f: bool(f.items[0].get("dof")), **_ONE_CAMERA)
ACTIONS += [Action("focus:point", "Focus on a point", rank=10, do="focus-point", **_DOF,
                   why="Turn on the camera's Depth of field first; then click where it should be sharp."),
            Action("focus:item", "Focus on an item", rank=11, do="focus-item", row="focusItem", row_label="Pick", **_DOF,
                   why="Turn on the camera's Depth of field first; then click the item to keep sharp.")]


def _has_2d(f) -> bool:
    from rostrum_core import project
    return bool(f.doc.folder) and bool(project.items(f.doc.folder, "2d"))


# Send to 2D (SPEC §12, send_qt.py): the shot's current render into a 2D scene as a live-linked 3D render layer. Offered only
# when the project has a 2D item (the Editor isn't built yet, so there is no Send to Editor).
ACTIONS.append(Action("shot:send", "Send to 2D", kinds=("shot",), max_targets=1, importance="secondary", rank=20, group="shot",
                      do="send-2d", valid=_has_2d, why="Send to 2D needs one shot selected and a 2D item in this project."))


# The edit block (the kit's EDIT_JOBS: right-click's last block, keys and Ctrl+K): Duplicate and Delete on one scene
# item, material or shot (adding.py); the shot the screen shows can't be deleted from under it.
COPIES = (*F.ITEMS, "material", "shot")
ACTIONS += [
    Action("item:duplicate", "Duplicate", kinds=COPIES, max_targets=1, job="duplicate", do="duplicate",
           why="Duplicate works on one item, material or shot."),
    Action("item:delete", "Delete", kinds=(*COPIES, "part"), max_targets=1, job="delete", do="delete",
           valid=lambda f: f.ids[0] != f.screen.get("shot_id"),
           why="Delete works on one item, material or shot; the shot shown here can't be deleted (open another first)."),
]
# Copy / Paste material (the shared Copy style / Paste style keys, in 3D's words): screen state until Paste makes its one change
_MATERIAL = dict(kinds=("mesh",), max_targets=1, importance="secondary", group="material")
ACTIONS += [
    Action("material:copy", "Copy material", rank=30, job="copy_style", do="copy-material", **_MATERIAL,
           valid=lambda f: bool(f.items[0].get("material")),
           why="Copy material needs one shape that has a material."),
    Action("material:paste", "Paste material", rank=31, job="paste_style", do="paste-material", **_MATERIAL,
           valid=lambda f: bool(f.screen.get("copied")) and f.doc.has(f.screen["copied"])
           and f.items[0].get("material") != f.screen["copied"],
           why="Copy a material first (right-click a shape › Copy material), then paste it on another shape."),
]


def _light(f) -> bool:
    return f.items[0].get("kind", "rect") != "dome"


ACTIONS += [
    Action("light:look", "Look through", kinds=("light",), max_targets=1, rank=12, group="light", do="look-through",
           valid=_light, why="Look through works on one light that shines one way (not the sky dome)."),
    Action("light:link", "Pick what it lights", kinds=("light",), max_targets=1, rank=13, group="light", do="link-lights",
           valid=_light, why="Pick what it lights works on one light (not the sky dome)."),
    Action("group:lipsync", "Lip sync…", kinds=("group",), max_targets=1, rank=14, group="animate", do="lipsync",
           valid=lambda f: mouths.is_mouth(f.items[0]),
           why="Lip sync works on a mouth group: a group whose items are the mouth's shapes."),
]
# Pose on (pose_qt.py): right-click on the clay. Back to rest: the Build page clears every turn, the Animate page keys
# the rest at the playhead (pose.rest). Joint names: the other naming (Plain / Humanoid), the joints found again.
_POSE = dict(kinds=("clay",), max_targets=1, importance="primary", group="pose", valid=lambda f: bool(f.screen.get("pose")))
ACTIONS += [
    Action("pose:rest", "Pose: back to rest", rank=3, do="pose-rest", **_POSE,
           why="Pose: back to rest works on the clay being posed (choose Pose in the rail first)."),
    Action("pose:find", "Find joints again", rank=4, do="pose-find", **_POSE,
           why="Find joints again works on the clay being posed (choose Pose in the rail first)."),
    Action("pose:names", lambda f: "Joint names: Plain" if f.items[0].get("jointNames") == "humanoid"
           else "Joint names: Humanoid", rank=5, do="pose-names", **_POSE,
           why="Joint names work on the clay being posed (choose Pose in the rail first)."),
]
# Copies and scatter (brief 24; copies_actions.py): Make copies ›, Scatter on, Change near ›
ACTIONS += COPIES_ACTIONS
# Simulate › Falls · Stays still · Off (brief 25; sim_actions.py): one folded row on right-click
ACTIONS += SIM_ACTIONS
# Project a picture from <shot> (brief 21b; project_qt.py): onto the selected shapes, from the shown shot's camera.
# Offered while painting, or with several shapes selected (walls, a set): a single shape's menu is full otherwise
# (the menu holds seven at most; while painting Make copies steps back for it).
ACTIONS += [
    Action("paint:project", lambda f: f'Project a picture from {f.screen.get("shot_name") or "the shot"}…', kinds=("mesh",),
           min_targets=1, importance="secondary", rank=48, group="paint", panel=False, do="paint-project",
           valid=lambda f: bool(f.screen.get("shot_id")) and (len(f.ids) > 1 or bool(f.screen.get("paint"))),
           why="Project a picture works on shapes (meshes) while painting, or on several shapes, with a shot to project from."),
]
# Empty space (nothing selected): the view's own
_NOTHING = dict(min_targets=0, max_targets=0, group="view")
ACTIONS += [
    Action("view:shot", "Back to the shot's view", rank=40, job="shot_view", do="shot-view", **_NOTHING,
           valid=lambda f: bool(f.screen.get("has_shot")) and f.screen.get("mode") != "shot",
           why="Back to the shot's view: the viewport isn't looking through the shot camera now."),
    Action("view:new_shot", "New shot from this view", rank=41, do="new-shot", **_NOTHING,
           valid=lambda f: bool(f.screen.get("can_shot")) and f.screen.get("mode") == "free",
           why="New shot from this view: turn the free camera to the view you want first."),
]
# The shown shot's own camera (shots.py, ops_shot_camera.py): Make this the shot whatever is selected (the header's button,
# Ctrl+Alt+0); Frame the selection on what can be framed (the crumb's list)
ACTIONS += [
    Action("view:take", "Make this the shot", min_targets=0, rank=39, group="view", job="take_view", do="take-view",
           valid=lambda f: bool(f.screen.get("has_shot")) and f.screen.get("mode") != "shot",
           why="Make this the shot: turn the view (right-drag) to the picture you want first."),
    Action("shot:frame", "Frame the selection", kinds=FRAMED, rank=42, group="view", job="frame_selection",
           do="frame-selection", valid=lambda f: bool(framed(f.doc, f.ids, f.screen.get("camera", ""))),
           why="Frame the selection works on shapes, clay, groups and lights (not the shot's own camera)."),
]
LIST = ActionList(ACTIONS, KEYS3D, noun="solid")
