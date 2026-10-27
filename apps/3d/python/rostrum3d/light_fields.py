"""A light's fields, part of the one table (fields.FIELDS["light"]; imported by fields.py once its helpers exist).

Product lighting (H21): softbox shapes (rect, disk, strip), how wide a panel throws its light (`spread`, a honeycomb
grid), the panel seen as a bright card (`card`), light linking (`lightsOnly`), a dome's `turn` and whether the camera
sees it (`seenByCamera`). What each renderer does with them: ENGINE_CONTRACT.md § 2, guides/lighting.md.
"""
from __future__ import annotations

import dataclasses

from .field_kit import ANY, C, CH, D, IS, N, NOT, S, T, TRANSFORM, X

KINDS = ["rect", "disk", "strip", "sphere", "spot", "distant", "dome"]
SPOT = IS("kind", "spot")
KIND_DEFAULTS = {"spot": {"radius": 0.05}}  # a kind's own starting values where they differ (build.make): a small bulb
PANELS = ANY("kind", "rect", "disk", "strip")
DOME = IS("kind", "dome")
NOT_DOME = NOT("kind", "dome")
DOC_ONLY = {"turn"}                 # the compiler turns it into the dome's ry; never sent to the core


def _away_on_domes(p):
    """A dome is around everything: where it stands, its tilt and its size mean nothing (its turn is `turn`)."""
    if p.name == "visible":
        return p
    when = NOT_DOME if p.valid_when is None else {"all": [p.valid_when, NOT_DOME]}
    return dataclasses.replace(p, valid_when=when)


LIGHT = [
    CH("kind", KINDS, "Kind", "Light", "rect",
       help="rect / disk: soft panels shining along their −Z; strip: a long thin panel (strip softbox); sphere: a "
            "bulb; spot: a bulb in a cone, for a pool of light; distant: the sun; dome: the sky or an HDR around everything"),
    N("length", "Length", "Shape", 0, 1e3, 0.01, "m", when=IS("kind", "strip"), default=1.2,
      help="Along the light's X"),
    N("width", "Width", "Shape", 0, 1e3, 0.01, "m", when=ANY("kind", "rect", "strip"), default=1.0,
      help="Rect: along its X. Strip: across it (along its Y), e.g. 0.15"),
    N("height", "Height", "Shape", 0, 1e3, 0.01, "m", when=IS("kind", "rect"), default=1.0),
    N("radius", "Radius", "Shape", 0, 1e3, 0.001, "m", when=ANY("kind", "disk", "sphere", "spot"), default=0.5,
      help="Disk: the panel's size. Sphere / spot: the bulb's size; smaller = crisper shadows (a new spot starts at 0.05)"),
    N("cone", "Cone", "Shape", 1, 179, 0.1, "°", when=SPOT, default=40.0,
      help="How wide the spot opens, edge to edge: smaller = a tighter pool of light"),
    N("softness", "Softness", "Shape", 0, 1, 0.01, when=SPOT, default=0.25,
      help="How gradually the edge of the pool fades: 0 = a hard edge, 1 = fading all the way from the middle"),
    N("angle", "Angle", "Shape", 0, 180, 0.01, "°", when=IS("kind", "distant"), default=0.53,
      help="How wide the sun looks; bigger = softer shadows (the real sun is 0.53°)"),
    X("texture", "HDR image", "Shape", "", when=DOME, help='Absolute .hdr / .exr path, a sky that comes with the app ("sky:studio"), or "" for a flat colour'),
    N("turn", "Turn", "Shape", -36000, 36000, 0.1, "°", when=DOME,
      help="Spins the sky around the up axis (moves the sun and the horizon's features)"),
    T("seenByCamera", "Seen by the camera", "Shape", True, S, DOME,
      help="Off: the dome still lights and shows in reflections, but the camera sees the shot's background"),
    C("color", "Colour", "Light", "#ffffff"),
    N("intensity", "Intensity", "Light", 0, 1e6, 0.01, default=1.0),
    N("exposure", "Exposure", "Light", -20, 20, 0.1, "stops", S, help="Each +1 doubles the light"),
    N("temperature", "Temperature", "Light", 0, 20000, 10, "K", S,
      help="Colour of the light in kelvin (2700 warm bulb, 5600 daylight, 7500 shade); 0 = off, use Colour only"),
    N("spread", "Spread", "Panel", 0, 180, 1, "°", S, PANELS, default=180.0,
      help="How wide the panel throws its light: 180 = all around its front (bare softbox); smaller = a "
           "honeycomb grid, a tighter pool with less spill (Cycles; not shown in the quick view)"),
    T("card", "Visible card", "Panel", False, S, PANELS,
      help="The panel itself shows to the camera as a bright card of its own brightness (reflections of it "
           "show in Cycles either way)"),
    X("lightsOnly", "Lights only", "Linking", "", D, NOT_DOME,
      help='Item ids separated by spaces: the light lights only these (and what is inside them); "" = everything '
           "(Cycles; the quick view lights everything)"),
    T("normalize", "Same brightness at any size", "Light", False, D,
      help="On: resizing the light changes its softness, not its brightness"),
    T("shadows", "Casts shadows", "Light", True, D),
] + [_away_on_domes(p) for p in TRANSFORM]
STILL = {"spread"}                  # set once per light, like a mesh's shape
FINAL_ONLY = {"spread", "lightsOnly"}   # Cycles only: the quick view can't show them (`notInQuickView`); the panel tags their rows "Final"
