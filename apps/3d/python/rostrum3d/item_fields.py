"""Every item type's field list (fields.py re-exports FIELDS): one entry per type, read by the field operations,
the inspector, the script layer and the compiler.
"""
from __future__ import annotations

import dataclasses

from rostrum_core import Param
from rostrum_core.keys import KEY_FIELDS

from .clay_fields import CLAY, STEP as CLAYSTEP
from .field_kit import CH, C, D, DOF, N, S, T, TRANSFORM, X, ANY
from .light_fields import LIGHT
from .material_fields import MATERIAL
from .mesh_fields import MESH
from .render_fields import RENDER
from .rig_fields import RIG

COMBINE_OPS = ["union", "subtract", "intersect"]
SOLIDS = ("mesh", "combine")                                   # what a combine combines

FIELDS: dict[str, list[Param]] = {
    "group": list(TRANSFORM),
    "mesh": MESH,                       # mesh_fields.py
    # A live boolean (Manifold, ops_combine.py): its children are the solids (meshes or combines), the first the base;
    # moving a child re-makes the result. The core draws only the result, never the children.
    "combine": [
        CH("op", COMBINE_OPS, "Operation", "Combine", "subtract",
           help="Union joins the solids; Subtract cuts every later one out of the first; Intersect keeps only where "
                "all of them overlap"),
        X("material", "Material", "Material", "", help='A material id, or "" for none', refers="material"),
    ] + TRANSFORM,
    "import": [
        X("file", "File", "File", "", help="Absolute path of a USD, glTF / GLB, OBJ, FBX or Alembic file; the file is never rewritten"),
        X("prim", "Prim", "File", "", D, help='Path inside the file; "" = its default prim'),
        X("material", "Material", "Material", "", S, help='One material over the whole import, or "" to keep the file\'s', refers="material"),
        N("fileUnit", "File unit", "File", 0, 1e6, 0.001, "m", D, default=1.0,
          help="Metres per unit of the file when it was imported and scaled to metres (1 = not rescaled); "
               "Keep original size (import.keep_size) undoes the rescale"),
    ] + TRANSFORM,
    # A part of an import: an override on a prim inside the file (path relative to the import's prim).
    "part": [
        X("path", "Path", "Part", "", D, help="Prim path relative to the import's prim, e.g. Body/Screen"),
        X("material", "Material", "Part", "", help='A material id, or "" to keep the file\'s', refers="material"),
        T("visible", "Visible", "Part", True),
    ],
    "clay": CLAY,                       # clay_fields.py: a lump to sculpt, its shape = its steps
    "claystep": CLAYSTEP,               # one piece or brush stroke of a clay, in order
    "light": LIGHT,                     # light_fields.py
    "camera": [
        N("focalLength", "Focal length", "Lens", 1, 2000, 0.1, "mm", default=50.0,
          help="Longer = narrower view and flatter perspective (product shots often 85–150)"),
        N("sensorWidth", "Sensor width", "Lens", 1, 100, 0.1, "mm", D, default=36.0),
        T("dof", "Depth of field", "Focus", False),
        N("fStop", "f-stop", "Focus", 0.5, 64, 0.1, "", when=DOF, default=2.8, help="Smaller = blurrier background"),
        N("focusDistance", "Focus distance", "Focus", 0.001, 1e5, 0.001, "m", default=5.0,
          when={"all": [DOF, ANY("focusItem", "", None)]}, help="How far in front of the camera things are sharp"),
        X("focusItem", "Focus on", "Focus", "", when=DOF, refers="item",
          help="Keep this item sharp: the focus distance follows it as it moves (its middle)"),
        N("near", "Near clip", "Clipping", 0.0001, 1e4, 0.001, "m", D, default=0.01),
        N("far", "Far clip", "Clipping", 0.01, 1e7, 1, "m", D, default=1000.0),
    ] + TRANSFORM,
    "material": MATERIAL,               # material_fields.py
    # A shot: a camera, a frame size and a stretch of time. Times are seconds; frames = round(seconds × fps),
    # from round(start × fps) to round(end × fps) − 1 (end is where the shot is over).
    "shot": [
        X("camera", "Camera", "Shot", "", help="The id of the camera this shot looks through", refers="camera"),
        N("fps", "Frame rate", "Shot", 1, 120, 1, "fps", integer=True, default=24),
        N("start", "Starts at", "Shot", 0, 36000, 0.001, "s"),
        N("end", "Ends at", "Shot", 0.001, 36000, 0.001, "s", default=2.0),
        N("width", "Width", "Frame", 16, 16384, 1, "px", S, integer=True, default=1920),
        N("height", "Height", "Frame", 16, 16384, 1, "px", S, integer=True, default=1080),
        C("background", "Background", "Frame", "#000000", S, help="What shows where nothing is (not a light)"),

        *RENDER,
    ],
    # A camera rig (rigs.py): holds the camera; its own transform is the base, without aim or scale.
    "rig": RIG + [dataclasses.replace(p, valid_when=None) for p in TRANSFORM
                  if p.name in ("x", "y", "z", "rx", "ry", "rz", "visible")],
    # A bone (ops_bones.py, skin.py): one link of a mesh's chain, in its parent's space (the mesh's own space for the
    # first, else the bone before it). It runs from its head (x y z) along its own +Y for `length`; turned rx, then
    # ry, then rz like any item. The person poses it only by its Turn (keys); the head is data the chain wrote.
    "bone": [
        N("x", "Head X", "Bone data", -1e5, 1e5, 0.001, "m", D),
        N("y", "Head Y", "Bone data", -1e5, 1e5, 0.001, "m", D),
        N("z", "Head Z", "Bone data", -1e5, 1e5, 0.001, "m", D),
        N("rx", "Turn X", "Rotation", -36000, 36000, 0.1, "°", help="Bends the bone (and the bones after it) forward or back"),
        N("ry", "Turn Y", "Rotation", -36000, 36000, 0.1, "°", help="Twists the bone around its own length"),
        N("rz", "Turn Z", "Rotation", -36000, 36000, 0.1, "°", help="Bends the bone sideways"),
        N("length", "Length", "Bone", 0.001, 1e4, 0.001, "m", S, default=0.1,
          help="From its head to its tail, where the next bone starts"),
        # a clay's joints (pose_joints.py): the part each bone is, and whether a person or agent placed it
        X("joint", "Part", "Bone data", "", D,
          help="The joint finder's part name: body, chest, head, arm.L, forearm.L, hand.L, leg.R, foot.R, tail, "
               "part3 … (empty on a chain laid by hand)"),
        T("placed", "Placed by hand", "Bone data", False, D,
          help="Moved by a person or an agent (pose.move_joint): kept where it is when the joints are found again"),
    ],
    "key": KEY_FIELDS,                   # the one key shape (t in seconds, v or c, ease), shared with 2D
    # A saved pose (ops_poses.py): values of some items' fields, applied as keys at the playhead.
    "pose": [
        Param.list("fields", "text", label="Fields", group="Pose data", importance=D, default=[],
                   help='What the pose holds, as "<item id>.<field>" (lid.rx)'),
        Param.list("values", "number", label="Values", group="Pose data", importance=D, min=-1e7, max=1e7, default=[],
                   help="One value per field, in the same order"),
    ],
}
