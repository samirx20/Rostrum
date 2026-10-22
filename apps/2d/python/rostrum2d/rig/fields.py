"""The fields of a rig and the items in it (RIG.md § The document). The Rust engine checks the same names and
kinds, so change RIG.md together with this table. Merged into `rostrum2d.fields.FIELDS` and `LABELS`."""
from __future__ import annotations

from ..fields import C, CH, D, IS, N, P, S, T, X, TRANSFORM  # noqa: F401  (the table helpers)

IK_ON = IS("mode", "ik")
BENDS = IS("bone2", "")
BENDING = {"not": BENDS}                    # a bind with a bone2 bends; without one it is rigid

FIELDS = {
    # A rig is a group of layers that also holds bones, iks and binds; its box is its px space.
    "rig": [
        N("w", "Width", "Box", 0, 20000, 1, "px", D, default=1920.0),
        N("h", "Height", "Box", 0, 20000, 1, "px", D, default=1080.0),
        T("clip", "Clip to box", "Box", False, S, help="Hide parts outside the rig's box"),
    ] + TRANSFORM,
    "bone": [
        X("parent", "Parent bone", "Bone", "", help='Id of the bone it hangs from; empty = a root bone'),
        N("rotation", "Turn", "Pose", -36000, 36000, 0.1, "°", help="Turn from rest; adds to the parent's turn"),
        N("scale", "Scale", "Pose", 0, 100, 0.01, "×", S, default=1.0, help="About the pivot; children and bound layers follow"),
        N("moveX", "Move X", "Pose", -20000, 20000, 1, "px", S, help="Shift of the pivot, in the parent's frame"),
        N("moveY", "Move Y", "Pose", -20000, 20000, 1, "px", S),
        N("x", "Pivot X", "Rest", -20000, 20000, 1, "px", S, help="Where the joint is at rest, in rig px"),
        N("y", "Pivot Y", "Rest", -20000, 20000, 1, "px", S),
        N("angle", "Direction", "Rest", -36000, 36000, 0.1, "°", S, help="Rest direction: 0 = right, 90 = down"),
        N("length", "Length", "Rest", 0, 20000, 1, "px", S, default=100.0),
    ],
    "ik": [
        X("bone", "Lower bone", "Chain", "", help="The shin or forearm; its parent is the upper bone"),
        CH("mode", ["ik", "fk"], "Pose by", "Chain", "ik", help="IK reaches the target; FK follows the bones' own turns"),
        N("chain", "Bones in chain", "Chain", 2, 32, 1, "", S, integer=True, default=2,
          help="2 = upper and lower bone (a leg); more = a spine, tail or arm with a hand, from the lower bone up"),
        N("targetX", "Target X", "Target", -20000, 20000, 1, "px", when=IK_ON, help="Where the lower bone's tip reaches to"),
        N("targetY", "Target Y", "Target", -20000, 20000, 1, "px", when=IK_ON),
        N("mix", "IK amount", "Target", 0, 1, 0.01, "", when=IK_ON, default=1.0, help="1 = reach the target, 0 = the FK pose"),
        CH("bend", ["clockwise", "counterclockwise"], "Knee bends", "Target", "clockwise", S, IK_ON,
           help="Which way the middle joint (knee, elbow) bends; a longer chain that starts straight curls this way"),
        N("pin", "Pin", "Target", 0, 1, 0.01, "", S, IK_ON, help="1 holds the target where it was when the pin turned on (a planted foot)"),
    ],
    "bind": [
        X("layer", "Layer", "Bind", "", help="A layer inside the rig"),
        X("bone", "Bone", "Bind", "", help="The bone it follows"),
        X("bone2", "Bends to", "Bind", "", help="A child bone of Bone: the layer bends across the joint; empty = rigid"),
        N("grid", "Mesh", "Bend", 4, 64, 1, "", S, BENDING, integer=True, default=24, help="Divisions along each side"),
        N("soft", "Soft joint", "Bend", 0, 5000, 1, "px", S, BENDING, default=40.0, help="Half-width of the blend; 0 = a hard crease"),
    ],
    # A saved pose (poses.py): its values {item id: {field: value}} are data, not fields.
    "pose": [X("note", "Note", "Pose", "", S, help="What the pose is for")],
}
LABELS = {"rig": "Rig", "bone": "Bone", "ik": "IK chain", "bind": "Bind", "pose": "Pose"}
OWNED_KEYS = ("bone", "ik")                 # these hold keys (their animatable fields)
STILL = {"bone": {"x", "y", "angle", "length"}, "ik": {"chain"}, "bind": {"grid", "soft"}}
