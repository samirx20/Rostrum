"""Every 2D item type's fields: the one table. The field operations, the inspector, the script layer's checks,
the scene description and its defaults all read it. Each field carries `valid_when` and `importance` (rule of
individuality: a control that doesn't apply right now is absent, never greyed).

Animatable = every number and colour field, a path's shape `d` (the engine morphs it) and its `widthProfile` (blended,
widthprofile.py), except those in STILL
(they describe the item, not a moment).
"""
from __future__ import annotations

from dataclasses import replace

from rostrum_core import Param
from rostrum_core.keys import KEY_FIELDS

from . import painting_fields as _painting, blends as _blends, group_bg as _group_bg, looping, fill_fields as _fill, grade_fields as _grade, layout_fields as _layout, paint_fields as _paint, stepped as _stepped, swap as _swap

NEW_FILL = "#d9d9d9"  # a new shape or path starts in this light grey: never the accent, so a selection shows on it (Figma's choice too)
IS = lambda name, value: {"is": [name, value]}  # noqa: E731
P = "primary"
S = "secondary"
D = "deep"


def N(name, label, group, lo, hi, step, unit="", imp=P, when=None, integer=False, default=0.0, help="", words=None,
      display="", shown="", on=None):      # display: how screens show it ("percent" = 1 is 100 %; the kit's ValueKinds.js)
    return Param.number(name, label=label, group=group, min=lo, max=hi, step=step, unit=unit, importance=imp,
                        valid_when=when, integer=integer, default=default, help=help, words=words or {}, display=display,
                        shown=shown, on=on)


def C(name, label, group, default, imp=P, when=None):
    return Param.color(name, label=label, group=group, importance=imp, valid_when=when, default=default)


RECT_WORDS = {"rect": "Rectangle"}
# A shape layer's kinds (the engine's shape_geom.rs draws all but rect and ellipse as their outline path).
SHAPE_KINDS = ["rect", "ellipse", "arc", "triangle", "polygon", "star", "line", "arrow", "spiral"]
SHAPE_WORDS = {"rect": "Rectangle", "ellipse": "Ellipse", "arc": "Arc", "triangle": "Triangle", "polygon": "Polygon",
               "star": "Star", "line": "Line", "arrow": "Arrow", "spiral": "Spiral"}
HEADS = ["none", "triangle", "open", "circle", "square", "bar"]
HEAD_WORDS = {"none": "None", "triangle": "Triangle", "open": "Open", "circle": "Circle", "square": "Square", "bar": "Bar"}
_OPEN = {"any": [IS("shape", "line"), IS("shape", "spiral")]}         # drawn as a line in the fill's paint
_LINES = {"any": [IS("shape", "line"), IS("shape", "spiral"), IS("shape", "arrow")]}


def CH(name, options, label, group, default, imp=P, when=None, help="", labels=None):
    return Param.choice(name, options, label=label, group=group, importance=imp, valid_when=when, default=default,
                        help=help, labels=labels or {})


def T(name, label, group, default, imp=P, when=None, help=""):
    return Param.toggle(name, label=label, group=group, importance=imp, valid_when=when, default=default, help=help)


def X(name, label, group, default, imp=P, help="", when=None, control="", filters=(), words=None, shown=""):
    return Param.text(name, label=label, group=group, importance=imp, valid_when=when, default=default, help=help,
                      control=control, filters=list(filters), words=words or {}, shown=shown)


BLENDS = _blends.BLENDS          # the one list (blends.txt), shared with the engine
MATTE_MODES = ["alpha", "alphaInverted", "luma", "lumaInverted"]

UNDER_CAMERA = {"fact": "underCamera"}      # a scene's own layer (every scene has its frame: kind.facts)

# When a layer shows, on the project's shared markers (retime.py).
TIMED = {"not": IS("marker", "")}
MARKER_TIMING = [
    X("marker", "Timed from marker", "Timing", "", S, control="pick",
      help="A shared marker's name: this layer's start, end and keys (and its children's) count from it, so moving the marker moves the layer (retime.py)"),
    X("endMarker", "Ends at marker", "Timing", "", S, control="pick", help="A shared marker's name: the layer is gone from that marker (Ends at is then absent)"),
]


def timing(start_help: str, end_help: str) -> list:
    """Starts at (before 0 is allowed: a lead-in before the layer's marker), Ends at (absent while it ends at a marker), and the markers."""
    return [N("start", "Starts at", "Timing", -36000, 36000, 0.01, "s", S, help=start_help + "; counted from Timed from marker when set, so -0.2 = just before it"),
            N("end", "Ends at", "Timing", 0, 36000, 0.01, "s", S, IS("endMarker", ""), default=36000.0, help=end_help,
              words={36000.0: "End of scene"}), *MARKER_TIMING]


# Riding a path layer (follow.py `layer.ride`); the engine's RIDE_AT (scene/fields.rs) is the same list.
RIDING = {"not": IS("ridePath", "")}
RIDE_AT = ["end", "start", "along"]      # the default is "along": a path set alone rides, and Along path is the setting to key
RIDE_AT_WORDS = {"end": "End of the drawn part", "start": "Start of the drawn part", "along": "A set place"}

# Riding a path layer beside it (engine: scene/follow.rs; rostrum2d/follow.py layer.ride): the layer's anchor (a
# frame: its centre) sits on that path on every frame, its own X, Y an offset from there. Every layer and the frame.
RIDE = [
    X("ridePath", "Rides path", "Ride", "", S, control="pick",       # screens: a choice of the layer's path siblings
      help="Id of a path layer in the same group or comp: this layer's anchor sits on it as it is reshaped, moved or "
           "drawn on, and X, Y become an offset from that point. Empty = none (layer.ride sets it)"),
    CH("rideAt", RIDE_AT, "Rides at", "Ride", "along", S, RIDING, labels=RIDE_AT_WORDS,
       help="The tip of the drawn-on part (Trim end), its start (Trim start), or a set place along the whole path"),
    N("rideAlong", "Along path", "Ride", 0, 1, 0.001, "", S, {"all": [RIDING, IS("rideAt", "along")]}, display="percent",
      help="How far along the path: 0 = its start, 1 = its end (key it to move along)"),
    T("rideTurn", "Turn with path", "Ride", False, S, RIDING, help="Adds the path's direction there to the layer's rotation"),
]

# Every layer has these (position is where its anchor sits in the composition, in px).
TRANSFORM = [      # x, y are absent while a group's auto layout places the layer (layout_fields.py)
    N("x", "X", "Transform", -20000, 20000, 1, "px", when=_layout.FREE_XY, default=960.0,
      help="Where the layer sits across the frame: move it left or right (position)"),
    N("y", "Y", "Transform", -20000, 20000, 1, "px", when=_layout.FREE_XY, default=540.0,
      help="Where the layer sits up and down the frame: move it up or down (position)"),
    N("scale", "Scale", "Transform", 0, 100, 0.01, "×", default=1.0, display="percent"),
    N("rotation", "Rotation", "Transform", -36000, 36000, 0.1, "°"),
    N("opacity", "Opacity", "Transform", 0, 1, 0.01, default=1.0, display="percent"),
    # Stretch: Scale's uneven part (a side handle's drag on the canvas sets it). Its row shows under Scale only while it
    # is uneven, never as a second scale control to look for.
    N("scaleX", "Stretch X", "Transform", 0, 100, 0.01, "×", default=1.0, display="percent", shown="changed",
      help="Scale across, on top of Scale"),
    N("scaleY", "Stretch Y", "Transform", 0, 100, 0.01, "×", default=1.0, display="percent", shown="changed",
      help="Scale up and down, on top of Scale"),
    N("anchorX", "Anchor X", "Anchor", -10, 10, 0.01, "", S, default=0.5, display="percent",
      help="The point it turns and scales around: 0 % = its left edge, 50 % = its centre, 100 % = its right edge"),
    N("anchorY", "Anchor Y", "Anchor", -10, 10, 0.01, "", S, default=0.5, display="percent",
      help="The point it turns and scales around: 0 % = its top edge, 50 % = its middle, 100 % = its bottom edge"),
    N("tiltX", "Tilt X", "Tilt", -180, 180, 0.1, "°", D, help="Turn around the horizontal axis, in perspective"),
    N("tiltY", "Tilt Y", "Tilt", -180, 180, 0.1, "°", D, help="Turn around the vertical axis, in perspective"),
    *timing("The layer appears at this time", "The layer is gone from this time"),
    Param.choice("blend", BLENDS, label="Blend", group="Blend", default="normal", importance=D, labels=_blends.LABELS,
                 help="How the layer mixes with the layers under it"),
    # The frame (frame/, apps/2d/FRAME.md): only a composition's own layers use these (kind.facts "underCamera").
    N("depth", "Depth", "Depth", -0.99, 1000, 0.01, "", D, UNDER_CAMERA,
      help="How far behind the frame's plane: 0 = on it, 1 = twice as far (moves half as much), -0.5 = nearer (twice as much)"),
    T("screenLock", "Pinned to frame", "Depth", False, D, UNDER_CAMERA, help="Moves with the frame, not the world: X, Y are in the frame's own px (a title, a logo bug, a border)"),
    # A track matte (engine: scene/matte.rs): the layer is seen through another layer beside it, drawn only as the matte.
    X("matte", "Track matte", "Matte", "", S, control="pick",       # screens: a choice of the layer's siblings
      help="Id of a layer in the same group or comp; this layer shows only where that one is drawn. Empty = none"),
    Param.choice("matteMode", MATTE_MODES, label="Matte uses", group="Matte", default="alpha", importance=S,
                 valid_when={"not": IS("matte", "")},
                 labels={"alpha": "Its shape", "alphaInverted": "Outside its shape", "luma": "Its brightness",
                         "lumaInverted": "Its darkness"},
                 help="Shape = where the matte layer is drawn; brightness = how light it is; the inverted ones swap"),
    *RIDE,
]
# Colour effects (grade_fields.py; engine: scene/grade.rs): only where there is a picture to grade.
GRADED = _grade.colour()
PICTURE_FILLED = _grade.colour(_fill.PICTURE[0].valid_when)        # a shape or path while it is filled with a picture

STROKE = IS("stroke", True)
# A path's stroke is varied when it has a taper or a width profile (ops_stroke.py; engine reads these fields).
VARIED = {"all": [STROKE, {"any": [{"not": IS("taperStart", 0)}, {"not": IS("taperEnd", 0)}, {"not": IS("widthProfile", "")}]}]}

# A text layer's type controls (engine: scene/stage_type.rs, letters.rs, type_font.rs).
NOT_FOLLOWING = IS("pathLayer", "")
ON_PATH = {"any": [{"not": IS("path", "")}, {"not": NOT_FOLLOWING}]}
BY_LETTER = {"not": IS("letterDelay", 0)}
FIGURES = ["default", "proportional lining", "tabular lining", "proportional old-style", "tabular old-style"]
TYPE = [
    T("ligatures", "Ligatures", "Type", True, D, help="Joined letters such as fi and fl, where the font has them"),
    CH("figures", FIGURES, "Number style", "Type", "default", S,
       help="Tabular numbers all have one width (they line up in counters); old-style numbers rise and fall like letters"),
    T("smallCaps", "Small caps", "Type", False, D, help="The font's own small capitals (refused if it has none)"),
    X("features", "Font features", "Type", "", D, help='OpenType features by tag, e.g. "ss01 ss03 salt" or "cv05=2"'),
    N("slant", "Slant", "Font", -90, 90, 0.1, "°", D, help="Variable font slant axis (slnt); negative leans right"),
    N("grade", "Grade", "Font", -1000, 1000, 1, "", D, help="Variable font grade axis (GRAD): heavier without getting wider"),
    X("axes", "Other axes", "Font", "", D, help='Any variable font axis by tag, e.g. "XTRA 468, CASL 1"', shown="script"),
    X("pathLayer", "Follows path", "On a path", "", S, control="pick", help="The id of a path layer beside it (same group): the letters sit on that path as it is "
      "reshaped, moved or drawn on, and the text takes its place and turn. Empty = not following one (text.follow sets it)"),
    X("path", "Path", "On a path", "", D, when=NOT_FOLLOWING, shown="script",      # SVG text: agents; people pick Follows path
      help="SVG path data (M L C Z) in the layer's own px; the letters sit on it. Empty = a normal line"),
    N("pathOffset", "Start along path", "On a path", -100000, 100000, 1, "px", S, ON_PATH,
      help="Moves the text along the path from where its alignment puts it"),
    CH("pathAlign", ["start", "center", "end"], "Align on path", "On a path", "start", S, ON_PATH),
    Param.choice("pathOverflow", ["hide", "straight"], label="Off the path", group="On a path", default="hide",
                 importance=S, valid_when=ON_PATH, labels={"straight": "Carry on straight"},
                 help="Letters that don't fit on the path: left out, or carried on in a straight line"),
    N("letterDelay", "Letter delay", "Letters", 0, 10, 0.005, "s", S,
      help="Each letter (or word) plays the layer's keys this much later than the one before; 0 = the layer moves as one"),
    CH("letterOrder", ["forward", "backward", "center", "random"], "Letter order", "Letters", "forward", S, BY_LETTER),
    N("letterSeed", "Random seed", "Letters", 0, 1000000, 1, "", D, {"all": [BY_LETTER, IS("letterOrder", "random")]},
      integer=True),
    CH("letterSplit", ["letters", "words"], "Split by", "Letters", "letters", S, BY_LETTER),
]

from .rig import fields as _rig  # noqa: E402  (rigs: the table is in rig/fields.py, merged below)
from .frame import fields as _frame  # noqa: E402  (the frame, the scene's camera: frame/fields.py, merged below)
from .motion import fields as _motion  # noqa: E402  (shutter, trails, smears: motion/fields.py, merged below)

# A text following a path layer takes these from the path (engine: scene/follow.rs TAKEN; rostrum2d/follow.py).
TAKEN = ("x", "y", "anchorX", "anchorY", "rotation", "scale", "scaleX", "scaleY", "tiltX", "tiltY")


def _unless_following(p: Param) -> Param:
    if p.name not in TAKEN:
        return p
    return replace(p, valid_when=NOT_FOLLOWING if p.valid_when is None else {"all": [p.valid_when, NOT_FOLLOWING]})


FILLED = T("filled", "Fill", "Fill", True)     # the fill's on/off switch: shapes and paths share it

FIELDS: dict[str, list[Param]] = {
    "comp": [
        N("width", "Width", "Frame", 16, 8192, 1, "px", integer=True, default=1920),
        N("height", "Height", "Frame", 16, 8192, 1, "px", integer=True, default=1080),
        N("fps", "Frame rate", "Frame", 1, 120, 1, "fps", integer=True, default=30),
        N("duration", "Length", "Frame", 0.04, 3600, 0.01, "s", default=5.0),
        C("background", "Background", "Look", "#000000"),
        X("soundtrack", "Soundtrack", "Sound", "", S, control="pick", words={"": "Main mix"},       # screens: the project's Sound items
          help="The RostrumSound item of this project that plays with this "
          "scene: the project's main mix by default (empty). Rendered by Sound's engine"),
    ],
    "shape": [
        CH("shape", SHAPE_KINDS, "Shape", "Shape", "rect", labels=SHAPE_WORDS),
        N("w", "Width", "Shape", 0, 20000, 1, "px", default=200.0, help="A line's or arrow's length"),
        N("h", "Height", "Shape", 0, 20000, 1, "px", default=200.0),
        N("radius", "Corner radius", "Shape", 0, 10000, 1, "px", when={"any": [{"all": [IS("shape", "rect"), IS("eachCorner", False)]},
                                                                         *(IS("shape", k) for k in ("triangle", "polygon", "star"))]}),
        T("eachCorner", "Each corner", "Shape", False, D, IS("shape", "rect"), help="A radius per corner"),
        *(N(f"radius{c}", f"Corner radius {w}", "Shape", 0, 10000, 1, "px", when={"all": [IS("shape", "rect"), IS("eachCorner", True)]})
          for c, w in (("TL", "top left"), ("TR", "top right"), ("BR", "bottom right"), ("BL", "bottom left"))),
        N("sides", "Sides", "Shape", 3, 60, 1, "", when=IS("shape", "polygon"), default=6.0),
        N("points", "Points", "Shape", 3, 60, 1, "", when=IS("shape", "star"), default=5.0),
        N("innerRadius", "Inner radius", "Shape", 0, 1, 0.01, "", when=IS("shape", "star"), default=0.5, display="percent"),
        N("innerCorner", "Inner corner radius", "Shape", 0, 10000, 1, "px", S, IS("shape", "star")),
        N("tip", "Tip position", "Shape", 0, 1, 0.01, "", when=IS("shape", "triangle"), default=0.5, display="percent",
          help="Where the top corner sits along the top edge"),
        N("hole", "Inner radius", "Shape", 0, 1, 0.01, "", when={"any": [IS("shape", "arc"), IS("shape", "spiral")]}, display="percent",
          help="Arc: 0 = a pie slice, more = a ring. Spiral: where it starts"),
        N("startAngle", "Start angle", "Shape", -360, 360, 1, "°", when=IS("shape", "arc"), help="0° = straight up, clockwise"),
        N("sweep", "Sweep", "Shape", -360, 360, 1, "°", when=IS("shape", "arc"), default=270.0),
        N("turns", "Turns", "Shape", 0.05, 100, 0.05, "", when=IS("shape", "spiral"), default=3.0),
        N("lineWidth", "Line width", "Shape", 0, 1000, 0.5, "px", when=_LINES, default=8.0),
        CH("lineCap", ["butt", "round", "square"], "Line ends", "Shape", "round", S, {"any": [IS("shape", "line"), IS("shape", "spiral")]},
           labels={"butt": "Flat", "round": "Round", "square": "Square"}),
        CH("headStart", HEADS, "Start head", "Shape", "none", when=IS("shape", "arrow"), labels=HEAD_WORDS),
        CH("headEnd", HEADS, "End head", "Shape", "triangle", when=IS("shape", "arrow"), labels=HEAD_WORDS),
        N("headSize", "Head size", "Shape", 0, 2000, 1, "px", when=IS("shape", "arrow"), default=32.0),
        FILLED,
        C("fill", "Fill colour", "Fill", NEW_FILL, when=IS("filled", True)),
        *_fill.OPACITY,
        T("stroke", "Outline", "Outline", False, S, when={"not": _OPEN}),
        C("strokeColor", "Outline colour", "Outline", "#ffffff", S, STROKE),
        N("strokeWidth", "Outline width", "Outline", 0, 500, 0.5, "px", S, STROKE, default=2.0),
        *_fill.PICTURE,
    ] + TRANSFORM + PICTURE_FILLED,
    "text": [
        X("body", "Text", "Text", "Text"),
        X("font", "Font", "Text", "Roboto Flex", control="pick"),       # screens: the fonts there are, each in its own face
        N("size", "Size", "Text", 1, 2000, 1, "px", default=96.0),
        N("weight", "Weight", "Text", 1, 1000, 1, "", default=600.0),
        T("italic", "Italic", "Text", False, S, when={"fact": "fontItalic"},
          help="The font's own italic (refused if the family has none)"),
        C("color", "Colour", "Text", "#ffffff"),
        *_fill.OPACITY,
        CH("align", ["left", "center", "right"], "Align", "Paragraph", "center", S),
        N("tracking", "Letter spacing", "Paragraph", -0.5, 2, 0.001, "em", S, help="Space between letters"),
        N("lineHeight", "Line height", "Paragraph", 0.5, 4, 0.01, "×", S, default=1.1),
        N("stretch", "Width", "Font", 25, 200, 1, "%", D, default=100.0, help="Variable font width"),
        N("boxWidth", "Box width", "Paragraph", 0, 20000, 1, "px", D, words={0: "Auto"},
          help="Auto (0) = one line, as wide as the text; a width wraps the words in it"),
        T("stroke", "Outline", "Outline", False, D),
        C("strokeColor", "Outline colour", "Outline", "#ffffff", D, STROKE),
        N("strokeWidth", "Outline width", "Outline", 0, 100, 0.5, "px", D, STROKE, default=1.0),
    ] + TYPE + [_unless_following(p) for p in TRANSFORM] + _grade.colour(_fill.PICTURE[0].valid_when),   # letters take no picture: never
    "image": [
        X("src", "File", "Image", "", help="Absolute path, or relative to the project folder", control="file",
          filters=["Pictures (*.png *.jpg *.jpeg *.webp *.tif *.tiff *.exr)"]),
        N("w", "Width", "Image", 0, 20000, 1, "px", default=640.0),
        N("h", "Height", "Image", 0, 20000, 1, "px", default=360.0),
        CH("fit", ["cover", "contain", "stretch"], "Fit", "Image", "cover", S),
        N("radius", "Corner radius", "Image", 0, 10000, 1, "px", S),
    ] + TRANSFORM + GRADED,
    # A video: its frames are decoded once (video.py) at the comp's fps and this size; the engine shows the frame the time asks for.
    # Source frame = floor((frame − start·fps) · speed) + round(offset·fps), looped or held at the last frame. No sound here.
    "video": [
        X("src", "File", "Video", "", help="Absolute path, or relative to the project folder", control="file",
          filters=["Videos (*.mp4 *.mov *.webm *.mkv *.avi)"]),
        N("w", "Width", "Video", 2, 8192, 1, "px", integer=True, default=640),
        N("h", "Height", "Video", 2, 8192, 1, "px", integer=True, default=360),
        CH("fit", ["cover", "contain", "stretch"], "Fit", "Video", "cover", S),
        N("radius", "Corner radius", "Video", 0, 10000, 1, "px", S),
        N("offset", "Clip starts at", "Video", 0, 36000, 0.01, "s", S, help="Seconds into the clip where the layer's first frame is taken"),
        N("speed", "Speed", "Video", 0, 100, 0.01, "×", S, default=1.0),
        CH("loop", looping.MODES, "Loop", "Video", "off", S, labels=looping.WORDS,
           help="What happens when the clip ends: Loop starts again, Ping-pong plays it back and forth (Off holds the last frame)"),
    ] + TRANSFORM + GRADED,
    # A Rostrum3D item's finished render, placed read-only (render3d.py): its EXR frames with their transparency, shown
    # as a video layer. Version 0 follows the newest render; Timed from marker puts its first frame on a marker (retime.py).
    "render3d": [
        X("item", "3D item", "3D render", "", help="Id of a Rostrum3D item of this project", control="pick"),   # screens: the rendered 3D items
        X("shot", "3D shot", "3D render", "", S, help="Id of the item's shot to show (empty = the newest render of any shot)",
          control="pick", words={"": "Newest of any shot"}),
        N("version", "Version", "3D render", 0, 100000, 1, "", S, integer=True, words={0: "Newest"},
          help="0 = always the newest render (follows new renders); a number keeps that version"),
        N("w", "Width", "3D render", 2, 8192, 1, "px", integer=True, default=1920),
        N("h", "Height", "3D render", 2, 8192, 1, "px", integer=True, default=1080),
        CH("fit", ["cover", "contain", "stretch"], "Fit", "3D render", "contain", S),
        N("radius", "Corner radius", "3D render", 0, 10000, 1, "px", D),
        N("offset", "Render starts at", "3D render", 0, 36000, 0.01, "s", D, help="Seconds into the render where the layer's first frame is taken"),
        N("speed", "Speed", "3D render", 0, 100, 0.01, "×", D, default=1.0),
        CH("loop", looping.MODES, "Loop", "3D render", "off", D, labels=looping.WORDS,
           help="What happens when the render ends: Loop starts again, Ping-pong plays it back and forth (Off holds the last frame)"),
    ] + TRANSFORM + GRADED,
    "group": [      # a size the auto layout hugs is absent: the layout sets it (layout_fields.py)
        N("w", "Width", "Box", 0, 20000, 1, "px", D, when=_layout.SIZE_SET["w"], default=1920.0),
        N("h", "Height", "Box", 0, 20000, 1, "px", D, when=_layout.SIZE_SET["h"], default=1080.0),
        T("clip", "Clip to box", "Box", False, S, help="Hide children outside the group's box"),
    ] + TRANSFORM + GRADED,
    # A drawing: painted strokes (the shared painting kit), one drawing per frame or held for several. Its canvas
    # is w × h px; untransformed it covers that box with the canvas's px = the composition's px.
    "drawing": [
        N("w", "Canvas width", "Drawing", 16, 8192, 1, "px", S, integer=True, default=1920),
        N("h", "Canvas height", "Drawing", 16, 8192, 1, "px", S, integer=True, default=1080),
        CH("loop", looping.MODES, "Loop", "Timing", "off", S, labels=looping.WORDS,
           help="Repeat the drawings for the layer's length: Loop starts again, Ping-pong goes back and forth (Off holds the last drawing)"),
    ] + TRANSFORM + GRADED,
    # A vector path (pathdata.py): `d` is absolute M, L, C, Z in the layer's own px from its box's top-left.
    # trimStart..trimEnd is the part of the stroke drawn (fractions of its length: the "draw on").
    "path": [
        X("d", "Path data", "Points", "", D, shown="script",       # people edit the points on the canvas
          help="Absolute M x y, L x y, C x1 y1 x2 y2 x y, Z in the layer's own px; the pen tool writes it. A new path has no points"),
        N("w", "Box width", "Box", 1, 20000, 1, "px", D, default=100.0, shown="script",     # the pen sets it from the points
          help="The box the anchor and gradients use"),
        N("h", "Box height", "Box", 1, 20000, 1, "px", D, default=100.0, shown="script"),
        FILLED,
        C("fill", "Fill colour", "Fill", NEW_FILL, when=IS("filled", True)),
        *_fill.OPACITY,
        CH("fillRule", ["nonzero", "evenodd"], "Fill rule", "Overlaps", "nonzero", D, IS("filled", True)),
        T("stroke", "Outline", "Outline", False),
        C("strokeColor", "Outline colour", "Outline", "#ffffff", when=STROKE),
        N("strokeWidth", "Outline width", "Outline", 0, 500, 0.5, "px", when=STROKE, default=4.0),
        CH("cap", ["butt", "round", "square"], "Ends", "Line ends", "round", S, STROKE),
        CH("join", ["miter", "round", "bevel"], "Corners", "Line ends", "round", S, STROKE),
        N("miter", "Miter limit", "Line ends", 1, 100, 0.1, "", D, {"all": [STROKE, IS("join", "miter")]}, default=4.0),
        N("dash", "Dash", "Dashes", 0, 10000, 0.5, "px", S, STROKE, help="0 = a solid line"),
        N("gap", "Gap", "Dashes", 0, 10000, 0.5, "px", S, STROKE, default=10.0),
        N("dashOffset", "Dash offset", "Dashes", -100000, 100000, 0.5, "px", D, STROKE, help="Animate it to march the dashes"),
        N("trimStart", "Trim start", "Draw on", 0, 1, 0.001, "", S, STROKE, help="Where the drawn part of the stroke starts (0..1)"),
        N("trimEnd", "Trim end", "Draw on", 0, 1, 0.001, "", S, STROKE, default=1.0, help="Animate 0 → 1 to draw the stroke on"),
        *_fill.PICTURE,
        N("taperStart", "Taper start", "Width", 0, 1, 0.01, "", S, STROKE, help="How much of the line the width takes to grow from 0 at the start (0..1)"),
        N("taperEnd", "Taper end", "Width", 0, 1, 0.01, "", S, STROKE, help="How much of the line the width takes to shrink to 0 at the end (0..1)"),
        Param.text("widthProfile", label="Width along the line", group="Width", importance=S, valid_when=STROKE, default="",
                   control="curve", max=4, help='"position,multiplier" pairs: position 0..1 along the line (increasing), multiplier of the '
                   'stroke width (0 or more). Empty = an even width (path.width sets it)'),
        Param.choice("taperAlong", ["line", "drawn"], label="Measured along", group="Width", default="line", importance=D,
                     valid_when=VARIED, labels={"line": "Whole line", "drawn": "Drawn part"},
                     help="Taper and profile follow the whole line, or only the part the trim shows"),
    ] + TRANSFORM + PICTURE_FILLED,
    # One drawing of a drawing layer: shown from frame `at` until the next drawing (held), none before the first.
    # It is a painting-kit canvas: it holds paint layers (`paints`) and paint masks.
    "frame": [
        N("at", "Frame", "Drawing", 0, 10**7, 1, "f", integer=True, help="The frame number this drawing appears at"),
    ],
    # Effects: a layer's look, in order (a gradient fills the shape, or the letters of a text).
    "blur": [N("radius", "Blur", "Blur", 0, 1000, 0.5, "px", default=12.0)],
    "glow": [
        N("radius", "Size", "Glow", 0, 1000, 0.5, "px", default=40.0),
        N("strength", "Strength", "Glow", 0, 4, 0.01, default=0.8),
        T("ownColor", "Layer's own colour", "Glow", True),
        C("color", "Colour", "Glow", "#ffffff", when=IS("ownColor", False)),
    ],
    "gradient": [
        CH("style", ["linear", "radial", "conic"], "Style", "Gradient", "linear"),
        N("angle", "Angle", "Gradient", -360, 360, 1, "°", when={"any": [IS("style", "linear"), IS("style", "conic")]},
          default=180.0, help="Linear: the way color1 runs to color2, as in CSS (0° = bottom to top, 90° = left to right, 180° = top to bottom). Conic: where the sweep starts (0° = straight up, clockwise)"),
        N("cx", "Centre X", "Gradient", -5, 6, 0.01, "", S, {"any": [IS("style", "radial"), IS("style", "conic")]},
          default=0.5, help="Fraction of the layer's box: 0 = left edge, 1 = right edge"),
        N("cy", "Centre Y", "Gradient", -5, 6, 0.01, "", S, {"any": [IS("style", "radial"), IS("style", "conic")]},
          default=0.5, help="Fraction of the layer's box: 0 = top edge, 1 = bottom edge"),
        C("color1", "From", "Gradient", "#ffffff"),
        C("color2", "To", "Gradient", "#808080"),
        T("middle", "Middle colour", "Gradient", False, S),
        C("color3", "Middle", "Gradient", "#c0c0c0", S, IS("middle", True)),
        N("mid", "Middle at", "Gradient", 0, 1, 0.01, "", S, IS("middle", True), default=0.5),
        *_fill.GEOMETRY,
    ],
    # Frosted glass: blurs what is behind the layer inside its box (and corner radius); the layer's own look is on top.
    "backdrop": [
        N("radius", "Blur", "Glass", 0, 300, 0.5, "px", default=24.0),
        N("fillAmount", "Layer shows at", "Glass", 0, 1, 0.01, "", S, default=1.0,
          help="How much of the layer's own look shows over the glass (a pale fill at 0.25 = frosted glass)"),
        N("saturate", "Colour boost", "Glass", 0, 4, 0.01, "×", S, default=1.0, help="1 = unchanged, above 1 = richer"),
        N("brightness", "Brightness", "Glass", 0, 3, 0.01, "×", D, default=1.0),
    ],
    # Film grain on the layer's own look (engine: scene/grain.rs), only where the layer is; a new picture each frame.
    "grain": [
        N("amount", "Amount", "Grain", 0, 1, 0.01, default=0.15, help="How strong: 0.1 = fine film, 0.4 = rough"),
        N("size", "Grain size", "Grain", 0.5, 16, 0.5, "px", default=1.5),
        T("colour", "Colour grain", "Grain", False, S, help="Off: grey grain. On: each colour has its own grain"),
        T("still", "Same each frame", "Grain", False, D, help="Off: the grain moves like film. On: a fixed texture"),
        N("seed", "Seed", "Grain", 0, 100000, 1, "", D, integer=True, default=1,
          help="A different seed is a different, equally random grain"),
    ],
    "shadow": [
        N("dx", "Offset X", "Shadow", -2000, 2000, 1, "px"),
        N("dy", "Offset Y", "Shadow", -2000, 2000, 1, "px", default=20.0),
        N("radius", "Softness", "Shadow", 0, 1000, 0.5, "px", default=40.0),
        C("color", "Colour", "Shadow", "#000000"),
        N("strength", "Strength", "Shadow", 0, 1, 0.01, default=0.5),
    ],
    # A mask: the part of the layer that shows (in the layer's own px, from its top-left corner).
    "mask": [
        CH("shape", ["rect", "ellipse"], "Shape", "Mask", "rect", labels=RECT_WORDS),
        N("x", "X", "Mask", -20000, 20000, 1, "px"),
        N("y", "Y", "Mask", -20000, 20000, 1, "px"),
        N("w", "Width", "Mask", 0, 20000, 1, "px", default=200.0),
        N("h", "Height", "Mask", 0, 20000, 1, "px", default=200.0),
        N("radius", "Corner radius", "Mask", 0, 10000, 1, "px", S, IS("shape", "rect")),
        N("feather", "Feather", "Mask", 0, 1000, 0.5, "px", S, help="Soft edge: this many px wide, centred on the edge"),
        T("invert", "Invert", "Mask", False, S),
        N("angle", "Rotation", "Mask", -360, 360, 0.1, "°", S, help="Turns the mask shape around its centre (a feathered rect sweeping across = a soft diagonal wipe)"),
    ],
    "key": KEY_FIELDS,         # the one key shape (rostrum_core.keys): t, v | c | d, ease and its curve
}

FIELDS["group"] += _layout.GROUP           # auto layout (layout.py): Python-side, baked into the children's keys
FIELDS["group"] += _swap.GROUP             # swap sets (swap.py): Python-side, shown as the children's opacity
FIELDS["group"] += _group_bg.FIELDS       # its own background (group_bg.py): drawn as a shape behind its layers
FIELDS.update(_rig.FIELDS)
FIELDS.update(_frame.FIELDS)
FIELDS.update(_motion.FIELDS)
FIELDS["comp"] += _motion.COMP + _stepped.COMP     # stepped timing (stepped.py): Python-side, applied in the scene
LAYERS = ("shape", "text", "image", "video", "render3d", "group", "drawing", "path", "rig", "camera")
# The layers a person or agent adds, deletes, copies, renames and stacks: every one but the frame (type "camera",
# frame/), which every scene holds exactly one of, made with the scene (frame/rules.py).
PLACED = tuple(t for t in LAYERS if t != "camera")
# Whether a layer can be picked or changed (locked) and whether it is drawn at all (hidden: not in the preview, not in an
# export; scene.py leaves it out). Document-only: the engine never sees them (scene.python_only). The frame can be
# locked (frame/fields.py), never hidden.
STATE = [T("locked", "Locked", "Layer", False, D, help="Locked: the screen won't pick or drag it and operations refuse it until it is unlocked"),
         T("hidden", "Hidden", "Layer", False, D, help="Not drawn, in the preview and in an export, until shown again")]
for _t in LAYERS:
    if _t != "camera":
        FIELDS[_t] += STATE + _layout.CHILD + ([_layout.CHILD_GROW] if _t in _layout.SIZED else [])
    FIELDS[_t] += _stepped.LAYER
for _t in _paint.TYPES:                    # paint on an element (paint_fields.py): its Paint group
    FIELDS[_t] += _paint.ELEMENT
FIELDS["drawing"] += _paint.DRAWING
for _t in _fill.OWNERS:                    # the fill as a paint (fill_fields.py): its type, gradient geometry, stops
    FIELDS[_t] += _fill.LAYER
FIELDS["stop"] = _fill.STOP
FIELDS["painting"] = _painting.FIELDS         # a painting of the scene (paintings.py)
FIELDS["swatch"] = [C("color", "Colour", "Colour", "#ffffff")]     # a project colour (ops_fill_paint.py)
EFFECTS = ("blur", "glow", "gradient", "backdrop", "shadow", "grain", *_motion.EFFECTS)
ANIMATED_OWNERS = LAYERS + EFFECTS + ("mask", "stop") + _rig.OWNED_KEYS
FIXED = {**_frame.FIXED}     # fields no <type>.set takes: the document writes them itself (the frame's home)
STILL = {"painting": {"w", "h", "newHold"}, "comp": {"width", "height", "fps", "duration", "background", *(p.name for p in _motion.COMP)}, "drawing": {"w", "h"}, "path": {"w", "h"},
         "group": {"columns"},
         "video": {"w", "h", "offset", "speed"},
         "render3d": {"w", "h", "offset", "speed", "version"},
         "text": {"letterDelay", "letterSeed"},
         **_rig.STILL, **_frame.STILL, **_motion.STILL, "*": {"start", "end", "boxWidth", "locked", "hidden", "paintW", "paintH", "fillPhase", "fillDriftX", "fillDriftY"}}
LABELS = {"comp": "Scene", "shape": "Shape", "text": "Text", "image": "Image", "video": "Video", "render3d": "3D render", "group": "Group", "drawing": "Drawing", "path": "Path", "frame": "Drawing frame", "painting": "Painting",
          "blur": "Blur", "glow": "Glow", "gradient": "Gradient", "backdrop": "Frosted glass", "shadow": "Shadow", "grain": "Grain", "mask": "Mask", "key": "Key", "stop": "Gradient stop", "swatch": "Project colour",
          **_rig.LABELS, **_frame.LABELS, **_motion.LABELS}

# Named text styles (text_styles.py): a style holds the type of a text, the same fields as a text's (one table); a text's
# `textStyle` names the style it follows. A style is never keyed (it is the look, not a moment).
STYLED = ("font", "size", "weight", "italic", "color", "tracking", "lineHeight", "stretch", "slant", "grade", "axes", "ligatures",
          "figures", "smallCaps", "features")
FIELDS["textstyle"] = [p for p in FIELDS["text"] if p.name in STYLED]
FIELDS["text"].append(X("textStyle", "Text style", "Font", "", S, control="pick",
                        help="The named text style this text follows (its font, size, weight, colour …): changing the style "
                             "changes the text. Empty = its own. Setting one of those fields by hand detaches it"))
STILL["textstyle"], LABELS["textstyle"] = set(STYLED), "Text style"


# What a kind's own tool starts it with where that differs from the field's default (the Text tool places a text by
# its top-left, left-aligned). The tool writes these; the settings panel counts them as unchanged (hooks.py starts).
STARTS = {"text": {"anchorX": 0.0, "anchorY": 0.0, "align": "left"}}


def param(kind: str, name: str) -> Param | None:
    return next((p for p in FIELDS.get(kind, ()) if p.name == name), None)


def defaults(kind: str) -> dict:
    return {p.name: p.default for p in FIELDS[kind]}


TEXT_KEYED = {("path", "d"), ("path", "widthProfile")}   # text fields keys drive; the key keeps the text in `d`


def animatable(kind: str) -> list[str]:
    """The fields of `kind` that keys may drive."""
    still = STILL.get(kind, set()) | STILL["*"]
    return [p.name for p in FIELDS.get(kind, ()) if (p.type in ("number", "color") or (kind, p.name) in TEXT_KEYED)
            and p.name not in still]


def key_field(kind: str, prop: str) -> str:
    """Where a key of `kind.prop` keeps its value: `c` (a colour), `d` (text: a path's shape or width profile) or `v` (a number)."""
    t = param(kind, prop).type
    return "c" if t == "color" else "d" if t == "text" else "v"
