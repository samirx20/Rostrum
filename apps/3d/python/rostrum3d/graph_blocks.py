"""The blocks a material's graph is made of (brief 23, the Blocks view): one catalogue, as data. The screen builds each
block's settings rows from its inputs (rostrum_core Params), the kit view draws its ports from their kinds, the ops
check values against them and graph_mtlx.py writes each block as a `rostrum_<type>` node of the Rostrum MaterialX
library (apps/3d/core/mtlx/rostrum_blocks.mtlx, apps/3d/stylized/mtlx/rostrum_stylized.mtlx).

Port kinds: colour (color3), number (float), normal (vector3), style (stylized settings). An input with a `kind` is a
port a wire can feed; one without is a setting only (a file, a choice, a ramp's stops). Surface is the material
itself: its linkable inputs are the material's own fields. Stylized blocks (Lines, Light to colour, Halftone) carry
the material's own fields of that group: their values ARE the material's (graph.py), and wiring one into Surface's
Style switches that setting on. Their own Style input chains another stylized block (Halftone → Lines → Surface).
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from rostrum_core import Param

from .material_fields import MATERIAL

KINDS = {"colour": "color3", "number": "float", "normal": "vector3", "style": "rostrum_style"}   # → MaterialX type
STYLIZED = {"lines": "lines", "lightToColour": "lightToColor", "halftone": "halftone"}        # block → its toggle
SURFACE_PORTS = {"baseColor": "colour", "roughness": "number", "metallic": "number", "emissionColor": "colour",
                 "normal": "normal", "style": "style"}
CHAIN = "then"          # a stylized block's Style input: another stylized block applied too (not a setting)


@dataclass
class Input:
    param: Param
    kind: str | None = None          # a port's kind; None = a setting only

    @property
    def name(self) -> str:
        return self.param.name

    def schema(self) -> dict:
        """The Param's own schema (what a settings row is built from) plus the port kind."""
        return {**self.param.to_dict(), "kind": self.kind, **({"control": self.param.control} if self.param.control else {})}


@dataclass
class Block:
    type: str
    label: str
    group: str
    inputs: list[Input]
    outputs: list[tuple[str, str, str]]          # (name, label, kind)
    words: list[str] = field(default_factory=list)
    note: str = ""                               # e.g. "Final only"
    summary: str = ""                            # the input the grey line under the title shows
    mtlx: str = ""                               # its MaterialX node: rostrum_<…>

    def input(self, name: str) -> Input | None:
        return next((i for i in self.inputs if i.name == name), None)

    def output(self, name: str):
        return next((o for o in self.outputs if o[0] == name), None)

    def defaults(self) -> dict:
        return {i.name: i.param.default for i in self.inputs if i.param.default is not None}


class Stops(Param):
    """A ramp's colour stops: [[position 0..1, "#rrggbb"], …], 2 to 8 of them (a ramp's own value type)."""

    def check(self, value, where: str):
        from rostrum_core import RostrumError, codes
        from rostrum_core import colours

        def bad(problem):
            raise RostrumError(codes.BAD_ARGUMENT, where, f"{self.name}={value!r}", problem, ['[[0, "#000000"], [1, "#ffffff"]]'],
                               "2 to 8 stops, each a position from 0 to 1 and a colour.")
        if not isinstance(value, (list, tuple)) or not 2 <= len(value) <= 8:
            bad("must be 2 to 8 stops")
        out = []
        for q in value:
            if not isinstance(q, (list, tuple)) or len(q) != 2 or isinstance(q[0], bool) or not isinstance(q[0], (int, float)) \
                    or not 0 <= q[0] <= 1 or (c := colours.read(q[1])) is None:
                bad(f"has a stop {q!r} that is not [position 0..1, colour]")
            out.append([float(q[0]), c])
        return sorted(out, key=lambda s: s[0])

    def json_schema(self) -> dict:
        return {"type": "array", "minItems": 2, "maxItems": 8, "description": self.help or "2 to 8 [position 0..1, \"#rrggbb\"]",
                "items": {"type": "array", "minItems": 2, "maxItems": 2}}


class Values(Param):
    """An op argument holding {setting name: value} (graph.add / graph.set): each value is checked per block type by
    graph.check_value, so only the shape is checked here."""

    def check(self, value, where: str):
        from rostrum_core import RostrumError, codes
        if not isinstance(value, dict) or not all(isinstance(k, str) for k in value):
            raise RostrumError(codes.BAD_ARGUMENT, where, f"{self.name}={value!r}", "must be {setting: value, …}",
                               ['{"scale": 8}'])
        return dict(value)

    def json_schema(self) -> dict:
        return {"type": "object", "description": self.help or self.label}


def _n(name, label, default, lo, hi, step, unit="", port="number", integer=False, help=""):
    return Input(Param.number(name, label=label, min=lo, max=hi, step=step, unit=unit, default=default, integer=integer,
                              help=help), port)


def _c(name, label, default, help=""):
    return Input(Param.color(name, label=label, default=default, help=help), "colour")


def _ch(name, label, options: dict, default):
    return Input(Param.choice(name, list(options), label=label, labels=options, default=default))


def _stylized_inputs(group: str, toggle: str) -> list[Input]:
    """A stylized block's settings: the material's own fields of that group, its switch left out (the wire is the
    switch); conditions on the switch dropped, the others kept (Softness shows with Smooth edges)."""
    out = []
    for p in MATERIAL:
        if p.group != group or p.name == toggle:
            continue
        when = p.valid_when
        if when == {"is": [toggle, True]}:
            when = None
        elif when and "all" in when:
            rest = [c for c in when["all"] if c != {"is": [toggle, True]}]
            when = rest[0] if len(rest) == 1 else ({"all": rest} if rest else None)
        out.append(Input(dataclasses.replace(p, valid_when=when, group="", importance="primary")))
    return out + [Input(Param.text(CHAIN, label="Then"), "style")]


def _style_in_label(inputs):
    inputs[-1].param.help = "Another stylized block applied too (chain them into Surface's Style)"
    return inputs


BLOCKS: list[Block] = [
    Block("image", "Image", "Pictures", [
        Input(Param.text("file", label="Picture", default="", control="file",
                         filters=["Pictures (*.png *.jpg *.jpeg *.exr *.tif *.tiff *.hdr)"],
                         help="Absolute path of a picture laid on the surface's unfolded surface (its UVs)")),
        _ch("colourData", "Holds", {"colour": "Colour", "data": "Numbers"}, "colour"),
    ], [("colour", "Colour", "colour"), ("value", "Value", "number")],
        words=["texture", "picture", "photo", "map", "file"], summary="file", mtlx="rostrum_image"),
    Block("noise", "Noise", "Patterns", [
        _n("scale", "Scale", 5.0, 0, 1000, 0.1, help="How many bumps per metre of the item"),
        _n("detail", "Detail", 2, 0, 15, 1, port=None, integer=True, help="Layers of smaller bumps over the big ones"),
        _n("roughness", "Roughness", 0.5, 0, 1, 0.01, help="How strong each smaller layer is"),
        _n("distortion", "Distortion", 0.0, 0, 100, 0.1, help="Swirls the pattern"),
    ], [("value", "Value", "number"), ("colour", "Colour", "colour")],
        words=["pattern", "cloud", "random", "grain", "procedural"], summary="scale", mtlx="rostrum_noise"),
    Block("mix", "Mix", "Colour", [
        _n("factor", "Factor", 0.5, 0, 1, 0.01, help="0 = A, 1 = B blended over A"),
        _c("a", "A", "#000000"),
        _c("b", "B", "#ffffff"),
        _ch("blend", "Blend", {"mix": "Mix", "multiply": "Multiply", "add": "Add", "screen": "Screen",
                               "overlay": "Overlay", "darken": "Darken", "lighten": "Lighten"}, "mix"),
    ], [("colour", "Colour", "colour")], words=["blend", "combine", "layer", "multiply"], summary="blend",
        mtlx="rostrum_mix"),
    Block("ramp", "Ramp", "Colour", [
        _n("factor", "Factor", 0.5, 0, 1, 0.01, help="Where on the ramp: 0 = the first stop, 1 = the last"),
        Input(Stops("stops", "points", label="Stops", default=[[0.0, "#000000"], [1.0, "#ffffff"]], control="stops")),
        _ch("interpolate", "Between stops", {"linear": "Linear", "constant": "Constant", "smooth": "Smooth"}, "linear"),
    ], [("colour", "Colour", "colour"), ("value", "Value", "number")],
        words=["gradient", "colour ramp", "map", "bands"], summary="stops", mtlx="rostrum_ramp"),
    Block("curve", "Curve", "Numbers", [
        _n("value", "Value", 0.5, 0, 1, 0.01),
        Input(Param.points("points", label="Points", min=2, max=2, default=[[0.0, 0.0], [1.0, 1.0]], control="points",
                           help="2 to 8 points, x and y from 0 to 1, joined by straight lines")),
    ], [("value", "Value", "number")], words=["remap", "levels", "float curve"], summary="points",
        mtlx="rostrum_curve"),
    Block("colourAdjust", "Colour adjust", "Colour", [
        _c("colour", "Colour", "#808080"),
        _n("hue", "Hue", 0.0, -0.5, 0.5, 0.01, help="Turns the hue: ±0.5 = half way round the colour wheel"),
        _n("saturation", "Saturation", 1.0, 0, 2, 0.01),
        _n("brightness", "Brightness", 1.0, 0, 2, 0.01),
        _n("contrast", "Contrast", 0.0, -1, 1, 0.01),
    ], [("colour", "Colour", "colour")], words=["hue", "saturation", "brightness", "contrast", "hsv"],
        mtlx="rostrum_colour_adjust"),
    Block("bevel", "Bevel shading", "Shape", [
        _n("radius", "Radius", 0.005, 0, 0.1, 0.001, "m", help="How far the rounding reaches from each edge"),
        _n("samples", "Samples", 8, 1, 64, 1, port=None, integer=True),
    ], [("normal", "Normal", "normal")], words=["round edges", "normal", "edge"], note="Final only",
        summary="radius", mtlx="rostrum_bevel"),
    Block("occlusion", "Ambient occlusion", "Shape", [
        _n("distance", "Distance", 0.2, 0, 10, 0.01, "m", help="How far around a point it looks for nearby surfaces"),
        _c("colour", "Colour", "#ffffff"),
    ], [("value", "Value", "number"), ("colour", "Colour", "colour")], words=["ao", "dirt", "cavity", "crevice"],
        note="Final only", summary="distance", mtlx="rostrum_occlusion"),
    Block("lines", "Lines", "Stylized", _style_in_label(_stylized_inputs("Lines", "lines")),
          [("style", "Style", "style")], words=["ink", "outline", "toon", "contour"], note="Stylized only",
          summary="linesWidth", mtlx="rostrum_lines"),
    Block("lightToColour", "Light to colour", "Stylized",
          _style_in_label(_stylized_inputs("Light to colour", "lightToColor")),
          [("style", "Style", "style")], words=["toon", "cel", "bands", "ramp shading"], note="Final · Stylized",
          mtlx="rostrum_light_to_colour"),
    Block("halftone", "Halftone", "Stylized", _style_in_label(_stylized_inputs("Halftone", "halftone")),
          [("style", "Style", "style")], words=["dots", "print", "comic", "screen"], note="Stylized only",
          summary="halftoneSize", mtlx="rostrum_halftone"),
]
BY_TYPE: dict[str, Block] = {b.type: b for b in BLOCKS}


def surface_block() -> Block:
    """Surface: the material itself. Its inputs are the material's own fields (set = material.set)."""
    params = {p.name: p for p in MATERIAL}
    own = {"normal": "Normal", "style": "Style"}          # wire-only inputs: no material field of their own
    inputs = [Input(params[n] if n in params else Param.text(n, label=own[n]), k) for n, k in SURFACE_PORTS.items()]
    return Block("surface", "Surface", "", inputs, [])


SURFACE = surface_block()


def get(type_: str) -> Block | None:
    return SURFACE if type_ == "surface" else BY_TYPE.get(type_)


def out_name(block_type: str, port: str) -> str:
    """The MaterialX output name of a block's port: the port's own, or "out" where an input has that name (a
    nodedef's inputs and outputs share one set of names: Colour adjust's colour, Curve's value)."""
    return "out" if get(block_type).input(port) else port


def ports(items) -> list[dict]:
    return [{"name": i.name, "label": i.param.label, "kind": i.kind} for i in items if i.kind]


def catalogue() -> list[dict]:
    """CONTRACT §4's catalogue (the add list), plus each type's settings schema and note."""
    return [{"type": b.type, "label": b.label, "group": b.group, "words": list(b.words), "inputs": ports(b.inputs),
             "outputs": [{"name": n, "label": lab, "kind": k} for n, lab, k in b.outputs],
             "settings": [i.schema() for i in b.inputs if i.name != CHAIN], **({"note": b.note} if b.note else {})}
            for b in BLOCKS]
