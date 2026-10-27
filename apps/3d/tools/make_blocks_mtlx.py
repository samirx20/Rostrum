"""Write the Rostrum MaterialX libraries from the blocks catalogue (brief 23): run after changing a block's inputs.

    python apps/3d/tools/make_blocks_mtlx.py

apps/3d/core/mtlx/rostrum_blocks.mtlx: one nodedef per block output, ND_<rostrum node>_<type> (its output named after
the block's port: value, colour, normal), each with a nodegraph in MaterialX standard nodes so Storm's MaterialX code
generator draws it (Final maps the nodedef to its Cycles node instead, core/src/material_blocks.cpp); plus
rostrum_grey (a number into a colour) and rostrum_brightness (a colour into a number). Quick-view simplifications:
Noise's Detail is whole layers; Bevel and Ambient occlusion show nothing (Final only); a ramp's / curve's stops come
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


def noise(t):
    body = [n("position", "pos", "vector3", i("space", "string", "object")),
            n("multiply", "scaled", "vector3", i("in1", "vector3", "#pos"), i("in2", "float", "@scale")),
            n("noise3d", "warp", "vector3", i("position", "vector3", "#scaled"), i("pivot", "float", 0)),
            n("multiply", "warped", "vector3", i("in1", "vector3", "#warp"), i("in2", "float", "@distortion")),
            n("add", "p", "vector3", i("in1", "vector3", "#scaled"), i("in2", "vector3", "#warped")),
            n("add", "octaves", "integer", i("in1", "integer", "@detail"), i("in2", "integer", 1)),
            n("fractal3d", "f", t, i("position", "vector3", "#p"), i("octaves", "integer", "#octaves"),
              i("lacunarity", "float", 2), i("diminish", "float", "@roughness")),
            n("multiply", "half", t, i("in1", t, "#f"), i("in2", "float", 0.5)),
            n("add", "mid", t, i("in1", t, "#half"), i("in2", "float", 0.5))]
    return body, "#mid"


def image(t):
    body = [n("image", "img", "color3", i("file", "filename", "@file"))]
    return body, ("#img" if t == "color3" else brightness("#img", body))


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


GRAPHS = {"noise": noise, "image": image, "mix": mix, "ramp": ramp, "curve": curve, "colourAdjust": colour_adjust,
          "bevel": bevel, "occlusion": occlusion}


def nodedef(name, node, ins, outs) -> list[str]:
    rows = [f'  <nodedef name="{name}" node="{node}" nodegroup="rostrum">']
    for nm, t, v in ins:
        uni = ' uniform="true"' if t in ("string", "filename") or nm in ("count", "blendIndex", "interpolateIndex") else ""
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
            ref = f'nodename="{src[1:]}"' if src[0] == "#" else f'interfacename="{src[1:]}"'
            rows += [f'  <nodegraph name="NG_{b.mtlx}_{t}" nodedef="{nd}">', *body,
                     f'    <output name="{out}" type="{t}" {ref}/>', "  </nodegraph>"]
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
