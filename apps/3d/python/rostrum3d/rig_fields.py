"""A camera rig's fields (part of the one table in fields.py). A rig is a holder: the camera (or anything) inside it
rides on it. Its own x y z / turns place the rig's base; the rig's moves (orbit angle, crane arm, dolly travel) and
the camera head's pan and tilt are numbers like any other, so they key. rigs.py turns them into a transform per frame.
"""
from __future__ import annotations

from rostrum_core import Param

IS = lambda name, value: {"is": [name, value]}  # noqa: E731
P, S, D = "primary", "secondary", "deep"
RIG_KINDS = ["orbit", "crane", "dolly"]
HANDHELD = IS("handheld", True)


def N(name, label, group, lo, hi, step, unit="", imp=P, when=None, default=0.0, help="", integer=False):
    return Param.number(name, label=label, group=group, min=lo, max=hi, step=step, unit=unit, importance=imp,
                        valid_when=when, default=default, help=help, integer=integer)


RIG = [
    Param.choice("rig", RIG_KINDS, label="Rig", group="Rig", importance=P, default="orbit",
                 help="orbit: circles the rig's centre, always facing it (turntables); crane: an arm from the base "
                      "that lifts and swings; dolly: a straight track forward from the base"),
    N("radius", "Distance", "Orbit", 0, 1e4, 0.01, "m", when=IS("rig", "orbit"), default=1.0,
      help="From the centre to the camera"),
    N("height", "Height", "Orbit", -1e4, 1e4, 0.01, "m", when=IS("rig", "orbit"), help="Above the centre"),
    N("angle", "Angle", "Orbit", -36000, 36000, 0.1, "°", when=IS("rig", "orbit"),
      help="Around the centre; key 0 → 360 for a turntable"),
    N("armLength", "Arm length", "Crane", 0, 1e3, 0.01, "m", when=IS("rig", "crane"), default=2.0),
    N("lift", "Arm lift", "Crane", -89, 89, 0.1, "°", when=IS("rig", "crane"), help="Up from level"),
    N("swing", "Arm swing", "Crane", -36000, 36000, 0.1, "°", when=IS("rig", "crane"), help="Around the base"),
    N("travel", "Travel", "Dolly", -1e4, 1e4, 0.01, "m", when=IS("rig", "dolly"),
      help="Along the track: forward (the way the rig faces) from the base"),
    N("pan", "Pan", "Head", -36000, 36000, 0.1, "°", S, help="The camera head turns left/right"),
    N("tilt", "Tilt", "Head", -90, 90, 0.1, "°", S, help="The camera head turns up/down"),
    Param.toggle("handheld", label="Handheld", group="Handheld", importance=S, default=False,
                 help="A gentle hand-held drift: smooth noise on the head, the same every render"),
    N("shake", "Amount", "Handheld", 0, 20, 0.01, "°", S, HANDHELD, default=0.4, help="How far the head drifts"),
    N("shakeFrequency", "Speed", "Handheld", 0.01, 20, 0.01, "Hz", S, HANDHELD, default=0.6,
      help="How often it drifts; under 1 reads as breathing, over 3 as nervous"),
    N("shakeMove", "Sway", "Handheld", 0, 1, 0.001, "m", D, HANDHELD, default=0.004, help="The camera body sways this much"),
    N("seed", "Seed", "Handheld", 0, 1e6, 1, "", D, HANDHELD, integer=True, default=0,
      help="Another number gives another drift of the same size"),
]
