"""The field makers and the conditions every 3D fields table is written with (fields.py re-exports them): N a
number, C a colour, CH a choice, T a toggle, X a text; IS / ANY / NOT conditions for `valid_when`; P / S / D importance;
and the Position / Turn / Scale / Aim / Follow / Stick / Timing fields every scene item shares (TRANSFORM).
"""
from __future__ import annotations

import dataclasses

from rostrum_core import Param

IS = lambda name, value: {"is": [name, value]}  # noqa: E731
ANY = lambda name, *values: {"any": [IS(name, v) for v in values]}  # noqa: E731
NOT = lambda name, value: {"not": IS(name, value)}  # noqa: E731
P, S, D = "primary", "secondary", "deep"


def N(name, label, group, lo, hi, step, unit="", imp=P, when=None, integer=False, default=0.0, help=""):
    return Param.number(name, label=label, group=group, min=lo, max=hi, step=step, unit=unit, importance=imp,
                        valid_when=when, integer=integer, default=default, help=help)


def C(name, label, group, default, imp=P, when=None, help=""):
    return Param.color(name, label=label, group=group, importance=imp, valid_when=when, default=default, help=help)


def CH(name, options, label, group, default, imp=P, when=None, help=""):
    return Param.choice(name, options, label=label, group=group, importance=imp, valid_when=when, default=default,
                        help=help)


def T(name, label, group, default, imp=P, when=None, help=""):
    return Param.toggle(name, label=label, group=group, importance=imp, valid_when=when, default=default, help=help)


def X(name, label, group, default="", imp=P, when=None, help="", refers=None):
    """A text field. `refers`: the item type its text is the id of ("material", "camera"); screens offer those items."""
    return Param.text(name, label=label, group=group, importance=imp, valid_when=when, default=default, help=help, kind=refers)


NO_AIM = IS("aim", "none")
FOLLOWS = NOT("follow", "")
ANIMATED = {"fact": "animated"}      # the item, or something inside it, has keys (animated_fact below)
ANIMATING = {"fact": "animating"}    # the person is animating: a screen's Animate page; always, for agents (kind.py)
SCULPTING = {"fact": "sculpting"}    # the Clay tool is on: a screen's tool; always, for agents (kind.py)
STEPS = {"smooth": 1, "on2": 2, "on3": 3}   # Timing: how many frames each value holds (compile.py)
TIMING = dataclasses.replace(
    CH("timing", list(STEPS), "Timing", "Timing", "smooth", S, {"all": [ANIMATED, ANIMATING]},
       help="On 2s / On 3s: every value holds for 2 or 3 frames (counted from the shot's start), the stepped look "
            "of hand-drawn animation, while the camera and anything else left Smooth moves every frame. A group's "
            "timing steps everything inside it; an item inside that sets its own On 2s / On 3s keeps its own"),
    labels={"smooth": "Smooth", "on2": "On 2s", "on3": "On 3s"})
TRANSFORM = [
    N("x", "X", "Position", -1e5, 1e5, 0.001, "m"),
    N("y", "Y", "Position", -1e5, 1e5, 0.001, "m", help="Up"),
    N("z", "Z", "Position", -1e5, 1e5, 0.001, "m", help="Towards the default camera"),
    N("rx", "Turn X", "Rotation", -36000, 36000, 0.1, "°", S, NO_AIM, help="Applied first (tilt)"),
    N("ry", "Turn Y", "Rotation", -36000, 36000, 0.1, "°", S, NO_AIM, help="Applied second (spin around up)"),
    N("rz", "Turn Z", "Rotation", -36000, 36000, 0.1, "°", S, NO_AIM, help="Applied last"),
    N("sx", "Scale X", "Scale", 0, 1000, 0.01, "×", D, default=1.0),
    N("sy", "Scale Y", "Scale", 0, 1000, 0.01, "×", D, default=1.0),
    N("sz", "Scale Z", "Scale", 0, 1000, 0.01, "×", D, default=1.0),
    N("px", "Pivot X", "Pivot", -1e5, 1e5, 0.001, "m", D,
      help="Where the item turns and scales around, from its own middle (D with the gizmo moves it)"),
    N("py", "Pivot Y", "Pivot", -1e5, 1e5, 0.001, "m", D),
    N("pz", "Pivot Z", "Pivot", -1e5, 1e5, 0.001, "m", D),
    T("visible", "Visible", "Display", True, S),
    CH("aim", ["none", "point", "item"], "Aim at", "Aim", "none", S,
       help="Point the item's −Z (where cameras and rect/disk lights face) at a point or another item; "
            "its rotation is then worked out every frame"),
    N("aimX", "Aim X", "Aim", -1e5, 1e5, 0.001, "m", S, IS("aim", "point")),
    N("aimY", "Aim Y", "Aim", -1e5, 1e5, 0.001, "m", S, IS("aim", "point")),
    N("aimZ", "Aim Z", "Aim", -1e5, 1e5, 0.001, "m", S, IS("aim", "point")),
    X("aimItem", "Aim at item", "Aim", "", S, IS("aim", "item"), help="The id of the item to look at (its origin)",
      refers="item"),
    N("roll", "Roll", "Aim", -36000, 36000, 0.1, "°", S, NOT("aim", "none"),
      help="Turns an aimed item around the way it points: 90 stands a strip light on end, tilts a camera's horizon"),
    X("follow", "Follow", "Follow", "", S, refers="item",
      help="Ride on another item (a bud on a case's lid): it moves and turns with that item from wherever it is. "
           "Key Amount to 0 to let go: it stays where it was let go (follow.py)"),
    N("followAmount", "Amount", "Follow", 0, 1, 0.05, "", S, FOLLOWS, default=1.0,
      help="1 = rides fully, 0 = let go (stays put). Key it: 0 until it is picked up, 1 while carried, 0 to let go"),
    T("followPose", "Follow the pose", "Follow", False, S, FOLLOWS,
      help="On a posed clay (or a mesh with bones): ride the bone nearest where it sits, so it bends with the pose "
           "there (an eye on a turned head). Off: ride the whole item"),
    X("stick", "Stick to", "Stick", "", S, refers="item",
      help="Stay on the surface of this mesh straight below as the item moves: its Y is then its height above that "
           "surface (off the surface's edge it keeps its own Y). A plane, disc, box, sphere, cylinder, cone, "
           "capsule or editable mesh"),
    TIMING,
]

POLY = IS("shape", "poly")       # an editable mesh (ops_mesh.py): made by mesh.edit from any shape or combine, never added
DOF = IS("dof", True)
