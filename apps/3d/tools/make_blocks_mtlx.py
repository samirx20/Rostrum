"""Write the Rostrum MaterialX libraries from the blocks catalogue (brief 23): run after changing a block's inputs.

    python apps/3d/tools/make_blocks_mtlx.py

apps/3d/core/mtlx/rostrum_blocks.mtlx: one nodedef per block output, ND_<rostrum node>_<type> (its output named after
the block's port: value, colour, normal), each with a nodegraph in MaterialX standard nodes so Storm's MaterialX code
generator draws it (Final maps the nodedef to its Cycles node instead, core/src/material_blocks.cpp); plus
rostrum_grey (a number into a colour) and rostrum_brightness (a colour into a number). Quick-view simplifications:
Pattern draws on the UVs with standard nodes (Final builds the same sums from Cycles' math nodes); Noise runs Cycles' own noise (core/mtlx/rostrum_cycles_noise.glsl), so Quick and Final draw the same pattern; its Detail
is whole layers; Bevel and Ambient occlusion show nothing (Final only); a ramp's / curve's stops come
in as pos1..8 / col1..8 (val1..8) with count. apps/3d/stylized/mtlx/rostrum_stylized.mtlx: the rostrum_style type
and the stylized blocks' nodedefs (no implementation: the stylized renderer reads the material's fields).
The inputs come from graph_mtlx.inputs, the same table documents are written with.
"""
from __future__ import annotations

import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP / "python"))

from rostrum3d import graph_blocks as B, graph_mtlx as X  # noqa: E402

LUMA = "0.2126, 0.7152, 0.0722"
WEAVE_SHADE = 0.45     # a weave's thread is this much darker at its edges than on top (core material_blocks.cpp too)


def i(name, t, ref):
    """An input: ref "@x" = the nodedef's input x, "#n" = node n's out, else a literal value."""
    if isinstance(ref, str) and ref[:1] == "@":
        return f'<input name="{name}" type="{t}" interfacename="{ref[1:]}"/>'
    if isinstance(ref, str) and ref[:1] == "#":
        return f'<input name="{name}" type="{t}" nodename="{ref[1:]}"/>'
    return f'<input name="{name}" type="{t}" value="{ref}"/>'


def n(cat, name, t, *ins):
    return f'    <{cat} name="{name}" type="{t}">' + "".join(ins) + f"</{cat}>"


def brightness(src: str, out: list) -> str:
    out += [n("luminance", "lum", "color3", i("in", "color3", src), i("lumacoeffs", "color3", LUMA)),
            n("extract", "grey", "float", i("in", "color3", "#lum"), i("index", "integer", 0))]
    return "#grey"


def noise(t):        # Cycles' own noise (rostrum_cycles_noise.glsl), so Quick draws the pattern Final draws
    body = [n("position", "pos", "vector3", i("space", "string", "object")),
            n("multiply", "scaled", "vector3", i("in1", "vector3", "#pos"), i("in2", "float", "@scale")),
            n("convert", "layers", "float", i("in", "integer", "@detail")),
            n("rostrum_cycles_noise", "cn", "multioutput", i("position", "vector3", "#scaled"),
              i("detail", "float", "#layers"), i("roughness", "float", "@roughness"),
              i("distortion", "float", "@distortion"))]
    return body, ("#cn.value" if t == "float" else "#cn.colour")


def image(t):
    body = [n("image", "img", "color3", i("file", "filename", "@file"))]
    return body, ("#img" if t == "color3" else brightness("#img", body))


def pattern(t):      # on the UVs: checks, stripes or a plain weave (graph_blocks.PATTERNS), picked by shapeIndex
    f = lambda name, cat, *ins: n(cat, name, "float", *ins)  # noqa: E731
    body = [n("texcoord", "uv", "vector2", i("index", "integer", 0)),
            n("rotate2d", "rot", "vector2", i("in", "vector2", "#uv"), i("amount", "float", "@turn")),
            n("multiply", "p", "vector2", i("in1", "vector2", "#rot"), i("in2", "float", "@repeats")),
            f("u", "extract", i("in", "vector2", "#p"), i("index", "integer", 0)),
            f("v", "extract", i("in", "vector2", "#p"), i("index", "integer", 1))]
    for k in ("u", "v"):     # whole cells, and each axis at twice the rate for the weave's threads
        body += [f(f"f{k}", "floor", i("in", "float", f"#{k}")),
                 f(f"{k}2", "multiply", i("in1", "float", f"#{k}"), i("in2", "float", 2)),
                 f(f"f{k}2", "floor", i("in", "float", f"#{k}2")),
                 f(f"r{k}2", "modulo", i("in1", "float", f"#{k}2"), i("in2", "float", 1)),
                 f(f"a{k}", "multiply", i("in1", "float", f"#r{k}2"), i("in2", "float", 3.14159265)),
                 f(f"h{k}", "sin", i("in", "float", f"#a{k}"))]
    body += [f("cs", "add", i("in1", "float", "#fu"), i("in2", "float", "#fv")),
             f("checks", "modulo", i("in1", "float", "#cs"), i("in2", "float", 2)),
             f("ru", "modulo", i("in1", "float", "#u"), i("in2", "float", 1)),
             f("stripes", "ifgreater", i("value1", "float", "@width"), i("value2", "float", "#ru"),
               i("in1", "float", 1), i("in2", "float", 0)),
             f("ws", "add", i("in1", "float", "#fu2"), i("in2", "float", "#fv2")),
             f("over", "modulo", i("in1", "float", "#ws"), i("in2", "float", 2)),
             f("height", "mix", i("fg", "float", "#hv"), i("bg", "float", "#hu"), i("mix", "float", "#over")),
             f("which", "switch", i("in1", "float", "#checks"), i("in2", "float", "#stripes"),
               i("in3", "float", "#over"), i("which", "integer", "@shapeIndex"))]
    if t == "float":
        body.append(f("val", "switch", i("in1", "float", "#checks"), i("in2", "float", "#stripes"),
                      i("in3", "float", "#height"), i("which", "integer", "@shapeIndex")))
        return body, "#val"
    body += [n("mix", "col", "color3", i("fg", "color3", "@b"), i("bg", "color3", "@a"), i("mix", "float", "#which")),
             f("hs", "multiply", i("in1", "float", "#height"), i("in2", "float", WEAVE_SHADE)),
             f("wshade", "add", i("in1", "float", "#hs"), i("in2", "float", 1 - WEAVE_SHADE)),
             f("shade", "switch", i("in1", "float", 1), i("in2", "float", 1), i("in3", "float", "#wshade"),
               i("which", "integer", "@shapeIndex")),
             n("multiply", "out", "color3", i("in1", "color3", "#col"), i("in2", "float", "#shade"))]
    return body, "#out"


def mix(t):
    a, b, f = "@a", "@b", "@factor"
    body = [n("multiply", "mul", "color3", i("in1", "color3", a), i("in2", "color3", b)),
            n("add", "sum", "color3", i("in1", "color3", a), i("in2", "color3", b)),
            n("min", "dark", "color3", i("in1", "color3", a), i("in2", "color3", b)),
            n("max", "light", "color3", i("in1", "color3", a), i("in2", "color3", b))]
    over = {"mix": b, "multiply": "#mul", "add": "#sum", "darken": "#dark", "lighten": "#light"}
    for k, src in over.items():
        body.append(n("mix", f"b_{k}", "color3", i("fg", "color3", src), i("bg", "color3", a), i("mix", "float", f)))
    body += [n("screen", "b_screen", "color3", i("fg", "color3", b), i("bg", "color3", a), i("mix", "float", f)),
             n("overlay", "b_overlay", "color3", i("fg", "color3", b), i("bg", "color3", a), i("mix", "float", f))]
    order = B.BY_TYPE["mix"].input("blend").param.options
    body.append(n("switch", "out", "color3", *[i(f"in{k + 1}", "color3", f"#b_{o}") for k, o in enumerate(order)],
                  i("which", "integer", "@blendIndex")))
    return body, "#out"


def stops(t: str, value_prefix: str, factor: str, smooth: bool):
    """Stop i blends over the ones before from pos(i-1) to pos(i), while i <= count."""
    body, prev = [], f"@{value_prefix}1"
    for k in range(2, X.MAX_STOPS + 1):
        s = f"s{k}"
        body += [n("subtract", f"{s}_d", "float", i("in1", "float", factor), i("in2", "float", f"@pos{k - 1}")),
                 n("subtract", f"{s}_w", "float", i("in1", "float", f"@pos{k}"), i("in2", "float", f"@pos{k - 1}")),
                 n("max", f"{s}_wm", "float", i("in1", "float", f"#{s}_w"), i("in2", "float", 1e-5)),
                 n("divide", f"{s}_r", "float", i("in1", "float", f"#{s}_d"), i("in2", "float", f"#{s}_wm")),
                 n("clamp", f"{s}_t", "float", i("in", "float", f"#{s}_r"), i("low", "float", 0), i("high", "float", 1))]
        t_ = f"#{s}_t"
        if smooth:
            body += [n("smoothstep", f"{s}_sm", "float", i("in", "float", t_), i("low", "float", 0), i("high", "float", 1)),
                     n("ifgreatereq", f"{s}_st", "float", i("value1", "float", factor), i("value2", "float", f"@pos{k}"),
                       i("in1", "float", 1), i("in2", "float", 0)),
                     n("switch", f"{s}_how", "float", i("in1", "float", t_), i("in2", "float", f"#{s}_st"),
                       i("in3", "float", f"#{s}_sm"), i("which", "integer", "@interpolateIndex"))]
            t_ = f"#{s}_how"
        body += [n("ifgreatereq", f"{s}_on", "float", i("value1", "integer", "@count"), i("value2", "integer", k),
                   i("in1", "float", t_), i("in2", "float", 0)),
                 n("mix", f"{s}_c", t, i("fg", t, f"@{value_prefix}{k}"), i("bg", t, prev), i("mix", "float", f"#{s}_on"))]
        prev = f"#{s}_c"
    return body, prev


def ramp(t):
    body, out = stops("color3", "col", "@factor", True)
    return body, (out if t == "color3" else brightness(out, body))


def curve(t):
    return stops("float", "val", "@value", False)


def colour_adjust(t):
    return [n("combine3", "amt", "vector3", i("in1", "float", "@hue"), i("in2", "float", "@saturation"),
              i("in3", "float", "@brightness")),
            n("hsvadjust", "hsv", "color3", i("in", "color3", "@colour"), i("amount", "vector3", "#amt")),
            n("add", "c", "float", i("in1", "float", "@contrast"), i("in2", "float", 1)),
            n("contrast", "adj", "color3", i("in", "color3", "#hsv"), i("amount", "float", "#c"),
              i("pivot", "float", 0.5))], "#adj"


def bevel(t):        # Final only: a flat normal (Storm's normal input reads a normal map: 0, 0, 1 = unchanged)
    return [n("constant", "flat", "vector3", i("value", "vector3", "0, 0, 1"))], "#flat"


def occlusion(t):    # Final only: no darkening in Quick
    if t == "float":
        return [n("constant", "one", "float", i("value", "float", 1))], "#one"
    return [n("dot", "col", "color3", i("in", "color3", "@colour"))], "#col"


GRAPHS = {"noise": noise, "pattern": pattern, "image": image, "mix": mix, "ramp": ramp, "curve": curve, "colourAdjust": colour_adjust,
          "bevel": bevel, "occlusion": occlusion}


def nodedef(name, node, ins, outs) -> list[str]:
    rows = [f'  <nodedef name="{name}" node="{node}" nodegroup="rostrum">']
    for nm, t, v in ins:
        uni = ' uniform="true"' if t in ("string", "filename") or nm in ("count", "blendIndex", "interpolateIndex", "shapeIndex") else ""
        rows.append(f'    <input name="{nm}" type="{t}"' + ("" if v is None else f' value="{X._fmt(t, v)}"') + f"{uni}/>")
    rows += [f'    <output name="{o}" type="{t}"/>' for o, t in outs] + ["  </nodedef>"]
    return rows


def blocks_library() -> str:
    rows = ['<?xml version="1.0"?>', '<materialx version="1.39">',
            "  <!-- Rostrum blocks: written by apps/3d/tools/make_blocks_mtlx.py from the blocks catalogue; don't edit -->"]
    for b in B.BLOCKS:
        if b.type in B.STYLIZED:
            continue
        ins = X.inputs(b.type, b.defaults())
        for port, _label, kind in b.outputs:
            t = B.KINDS[kind]
            nd = f"ND_{b.mtlx}_{t}"
            body, src = GRAPHS[b.type](t)
            out = B.out_name(b.type, port)
            rows += nodedef(nd, b.mtlx, ins, [(out, t)])
            node, _, port = src[1:].partition(".")         # "#node.output": one output of a multi-output node
            ref = (f'nodename="{node}"' + (f' output="{port}"' if port else "")) if src[0] == "#" else f'interfacename="{node}"'
            rows += [f'  <nodegraph name="NG_{b.mtlx}_{t}" nodedef="{nd}">', *body,
                     f'    <output name="{out}" type="{t}" {ref}/>', "  </nodegraph>"]
    rows += ['  <nodedef name="ND_rostrum_cycles_noise" node="rostrum_cycles_noise" nodegroup="rostrum">',
             '    <input name="position" type="vector3" value="0, 0, 0"/>', '    <input name="detail" type="float" value="2"/>',
             '    <input name="roughness" type="float" value="0.5"/>', '    <input name="distortion" type="float" value="0"/>',
             '    <output name="value" type="float"/>', '    <output name="colour" type="color3"/>', "  </nodedef>",
             '  <implementation name="IM_rostrum_cycles_noise_genglsl" nodedef="ND_rostrum_cycles_noise"'
             ' file="rostrum_cycles_noise.glsl" function="mx_rostrum_cycles_noise" target="genglsl"/>']
    rows += nodedef("ND_rostrum_grey_color3", "rostrum_grey", [("in", "float", 0.0)], [("out", "color3")])
    rows += ['  <nodegraph name="NG_rostrum_grey_color3" nodedef="ND_rostrum_grey_color3">',
             n("convert", "c", "color3", i("in", "float", "@in")), '    <output name="out" type="color3" nodename="c"/>',
             "  </nodegraph>"]
    rows += nodedef("ND_rostrum_brightness_float", "rostrum_brightness", [("in", "color3", "#000000")], [("out", "float")])
    body = []
    brightness("@in", body)
    rows += ['  <nodegraph name="NG_rostrum_brightness_float" nodedef="ND_rostrum_brightness_float">', *body,
             '    <output name="out" type="float" nodename="grey"/>', "  </nodegraph>"]
    return "\n".join(rows + ["</materialx>", ""])


def stylized_library() -> str:
    rows = ['<?xml version="1.0"?>', '<materialx version="1.39">',
            "  <!-- Rostrum stylized blocks: written by apps/3d/tools/make_blocks_mtlx.py; don't edit. Their values are"
            " the material's own fields; the stylized renderer reads those, so these have no implementation -->",
            '  <typedef name="rostrum_style"/>']
    for b in B.BLOCKS:
        if b.type in B.STYLIZED:
            rows += nodedef(f"ND_{b.mtlx}", b.mtlx, X.inputs(b.type, b.defaults()), [("style", "rostrum_style")])
    return "\n".join(rows + ["</materialx>", ""])


def main():
    for rel, text in (("core/mtlx/rostrum_blocks.mtlx", blocks_library()),
                      ("stylized/mtlx/rostrum_stylized.mtlx", stylized_library())):
        out = APP / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(out)


if __name__ == "__main__":
    main()
