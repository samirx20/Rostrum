"""The toy document kind: a small stand-in app document shared by the core tests, the MCP demo server and the
GUI kit demo. Its controls are the S3 mockup's (proofs/gui-mock/controls.json), so the inspector can show the
rule of individuality on real operations. Not an app: apps register their own kinds the same way.
"""
from __future__ import annotations

from .document import Document
from .kind import DocKind
from .params import Param
from .registry import Registry

IS = lambda name, value: {"is": [name, value]}  # noqa: E731
DOF, BLADES = IS("dof", True), {"all": [IS("dof", True), IS("bokeh", "Blades")]}


def N(name, label, group, lo, hi, step, unit="", imp="primary", when=None, integer=False):
    return Param.number(name, label=label, group=group, min=lo, max=hi, step=step, unit=unit, importance=imp,
                        valid_when=when, integer=integer)


FIELDS = {
    "camera": [
        N("focal", "Focal length", "Lens", 12, 200, 1, "mm"),
        Param.toggle("dof", label="Depth of field", group="Lens"),
        N("focusDistance", "Focus distance", "Lens", 0.1, 50, 0.1, "m", when=DOF),
        N("aperture", "Aperture", "Lens", 1.2, 22, 0.1, "f/", "secondary", DOF),
        Param.choice("bokeh", ["Round", "Blades"], label="Bokeh shape", group="Lens", importance="secondary",
                     valid_when=DOF),
        N("blades", "Blade count", "Lens", 3, 12, 1, "", "secondary", BLADES, integer=True),
        Param.toggle("motionBlur", label="Motion blur", group="Shutter", importance="secondary"),
        N("shutter", "Shutter angle", "Shutter", 1, 360, 1, "°", "secondary", IS("motionBlur", True)),
        N("sensor", "Sensor width", "Shutter", 8, 70, 0.1, "mm", "deep"),
    ],
    "light": [
        Param.choice("type", ["Point", "Spot", "Area", "Sun"], label="Type", group="Light"),
        N("brightness", "Brightness", "Light", 0, 100, 0.5),
        Param.color("color", label="Colour", group="Light"),
        N("radius", "Size", "Shape", 0, 5, 0.05, "m", "secondary", IS("type", "Point")),
        N("cone", "Cone angle", "Shape", 1, 180, 1, "°", when=IS("type", "Spot")),
        N("coneSoftness", "Cone softness", "Shape", 0, 1, 0.01, "", "secondary", IS("type", "Spot")),
        N("width", "Width", "Shape", 0.01, 10, 0.01, "m", when=IS("type", "Area")),
        N("height", "Height", "Shape", 0.01, 10, 0.01, "m", when=IS("type", "Area")),
        N("sunAngle", "Sun size", "Shape", 0, 10, 0.1, "°", "secondary", IS("type", "Sun")),
        Param.toggle("shadows", label="Shadows", group="Shadows", importance="secondary"),
        N("shadowSoftness", "Shadow softness", "Shadows", 0, 1, 0.01, "", "secondary",
          {"all": [IS("shadows", True), {"not": IS("type", "Sun")}]}),
        N("samples", "Shadow samples", "Shadows", 1, 256, 1, "", "deep", IS("shadows", True), integer=True),
    ],
    "rect": [
        N("x", "X", "Position", -4000, 4000, 1, "px"), N("y", "Y", "Position", -4000, 4000, 1, "px"),
        N("w", "Width", "Size", 0, 8000, 1, "px"), N("h", "Height", "Size", 0, 8000, 1, "px"),
        Param.color("fill", label="Fill", group="Look"),
        N("radius", "Corner radius", "Look", 0, 1000, 1, "px", "secondary"),
    ],
    "text": [
        Param.text("body", label="Text", group="Text"),
        N("size", "Size", "Text", 1, 800, 1, "px"),
        Param.color("color", label="Colour", group="Text"),
        N("x", "X", "Position", -4000, 4000, 1, "px", "secondary"),
        N("y", "Y", "Position", -4000, 4000, 1, "px", "secondary"),
        Param.toggle("animateOn", label="Animate on", group="Animation"),
        N("letterDelay", "Letter delay", "Animation", 0, 1, 0.01, "s", when=IS("animateOn", True)),
        Param.choice("direction", ["Forward", "Backward", "Random"], label="Direction", group="Animation",
                     valid_when=IS("animateOn", True)),
        N("seed", "Seed", "Animation", 0, 9999, 1, "", "secondary",
          {"all": [IS("animateOn", True), IS("direction", "Random")]}, integer=True),
        N("tracking", "Tracking", "Text", -200, 200, 1, "", "deep"),
    ],
}
DEFAULTS = {
    "camera": dict(focal=50, dof=False, focusDistance=2.4, aperture=2.8, bokeh="Round", blades=7,
                   motionBlur=False, shutter=180, sensor=36),
    "light": dict(type="Area", brightness=12, color="#ffe2c4", radius=0.1, cone=45, coneSoftness=0.2,
                  width=1.2, height=0.8, sunAngle=0.5, shadows=True, shadowSoftness=0.6, samples=16),
    "rect": dict(x=0, y=0, w=200, h=120, fill="#4c8dff", radius=8),
    "text": dict(body="Hello", size=48, color="#ececec", x=0, y=0, animateOn=False, letterDelay=0.04,
                 direction="Forward", seed=1, tracking=0),
}
LABELS = {"camera": "Camera", "light": "Light", "rect": "Rectangle", "text": "Text"}
REGISTRY = Registry()


def _set_fields(ctx, targets, args):
    for t in targets:
        for k, v in args.items():
            ctx.set(t, k, v)


for _kind, _params in FIELDS.items():
    REGISTRY.operation(f"{_kind}.set", f"Change a {LABELS[_kind].lower()}'s settings.", target=_kind,
                       params=_params, label=f"Edit {LABELS[_kind].lower()}", fields=True)(_set_fields)


@REGISTRY.operation("layer.add", "Add a camera, light, rectangle or text.", params=[
    Param.choice("type", list(FIELDS), label="Type", required=True),
    Param.text("id", label="Id", help="Optional; counted per type when left out (rect_1, rect_2 …)."),
    Param.text("name", label="Name")], label="Add layer")
def layer_add(ctx, targets, args):
    t = args["type"]
    id_ = args.get("id") or ctx.new_id(t)
    ctx.insert("root", "layers", {"id": id_, "type": t, "name": args.get("name", LABELS[t]), **DEFAULTS[t]})


@REGISTRY.operation("layer.remove", "Delete layers.", target=tuple(FIELDS), label="Delete", importance="secondary")
def layer_remove(ctx, targets, args):
    for t in targets:
        ctx.remove(t)


@REGISTRY.operation("layer.rename", "Rename a layer.", target=tuple(FIELDS), label="Rename",
                    params=[Param.text("name", label="Name", required=True)], importance="secondary")
def layer_rename(ctx, targets, args):
    for t in targets:
        ctx.set(t, "name", args["name"])


@REGISTRY.operation("layer.move", "Move rectangles and texts to a position.", target=("rect", "text"),
                    label="Move", params=[N("x", "X", "Position", -4000, 4000, 1, "px"),
                                          N("y", "Y", "Position", -4000, 4000, 1, "px")])
def layer_move(ctx, targets, args):
    _set_fields(ctx, targets, args)


def _check(data) -> list[str]:
    names = [it["id"] for it in data.get("layers", [])]
    return [] if len(names) == len(set(names)) else ["two layers share an id"]


KIND = DocKind("toy", ".toy", REGISTRY, lists={"doc": ["layers"]}, check=_check,
               new=lambda: {"id": "root", "type": "doc", "layers": []})


def sample(folder=None, item=None) -> Document:
    """A document with one of each: cam_1, key (a light), card (a rect), title (a text)."""
    layers = [("cam_1", "camera", "Main camera"), ("key", "light", "Key light"), ("card", "rect", "Card"),
              ("title", "text", "Title")]
    data = KIND.blank()
    data["layers"] = [{"id": i, "type": t, "name": n, **DEFAULTS[t]} for i, t, n in layers]
    return Document(KIND, data, folder, item)
