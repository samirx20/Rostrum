"""Cycles shader graphs for the still life, written as UsdShade (info:id = "cycles_<node>").

Each material reads paint/textures/<name>.png (albedo, sRGB) and, when present,
<name>_height.png (bump, raw) and <name>_rough.png (roughness, raw). Tangent-space normal
maps are refused: the delegate makes no tangents, so they would silently do nothing. The background card is emissive (a matte painting, not lit).
--ramp mode swaps real shading for a key-light colour ramp built from Cycles nodes:
lit = max(N.L, 0) * (1 - raycast(P, L).is_hit)  ->  rgb_ramp  ->  multiply albedo  ->  emission.
"""
import os, re

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.normpath(os.path.join(HERE, "..", "paint", "textures"))

SURFACE = {  # principled_bsdf extras per material; bump = (strength, distance cm)
    "Table": dict(bsdf=dict(roughness=0.55), bump=(0.6, 0.15)),
    "Cloth": dict(bsdf=dict(roughness=0.95, sheen_weight=0.4), bump=(0.4, 0.08)),
    "Jug":   dict(bsdf=dict(roughness=0.2, coat_weight=0.4, coat_roughness=0.08), bump=(0.25, 0.04)),
    "Bowl":  dict(bsdf=dict(roughness=0.35), bump=(0.3, 0.05)),
    "Pear":  dict(bsdf=dict(roughness=0.5, subsurface_weight=0.15, subsurface_scale=0.4),
                  bump=(0.35, 0.03)),
}
# key-light ramp (dark -> lit), 16 steps; painted-light colours, multiplied with the albedo
RAMP = [(0.20, 0.22, 0.42)] * 1 + [(0.55, 0.45, 0.55)] * 2 + [(1.1, 0.92, 0.72)] * 7 + [(1.3, 1.08, 0.82)] * 6


def tex_path(name):
    return os.path.join(TEX, name + ".png").replace("\\", "/")


class Vec(tuple):
    """A direction/vector parameter (written as vector3f, never as a colour)."""


def fmt(v):
    if isinstance(v, Vec):
        return "vector3f", "(" + ", ".join("%.6g" % x for x in v) + ")"
    if isinstance(v, bool):
        return "bool", "true" if v else "false"
    if isinstance(v, (int, float)):
        return "float", repr(float(v))
    if isinstance(v, str) and v.startswith("@"):
        return "asset", v
    if isinstance(v, str):
        return "token", f'"{v}"'
    if isinstance(v, tuple):
        return ("color3f" if len(v) == 3 else "float2"), "(" + ", ".join("%.5g" % x for x in v) + ")"
    if isinstance(v, list) and isinstance(v[0], tuple):
        return "color3f[]", "[" + ", ".join("(%.5g, %.5g, %.5g)" % c for c in v) + "]"
    return "float[]", "[" + ", ".join("%.5g" % x for x in v) + "]"


def shader(mat, name, node, params=(), links=()):
    """links: (input, 'Node.output'). Outputs are declared by the consumers' connections."""
    lines = [f'        def Shader "{name}"', "        {", f'            uniform token info:id = "cycles_{node}"']
    for k, v in dict(params).items():
        t, s = fmt(v)
        lines.append(f"            {t} inputs:{k} = {s}")
    for k, src in links:
        n, o = src.split(".")
        lines.append(f"            float inputs:{k}.connect = </Looks/{mat}/{n}.outputs:{o}>")
    return "\n".join(lines + ["        }"])


def image(mat, name, file, raw):
    if not os.path.exists(file):
        raise SystemExit(f"missing texture: {file}")
    return shader(mat, name, "image_texture",
                  {"filename": f"@{file}@", "colorspace": "Raw" if raw else "sRGB Encoded Rec.709 (sRGB)"})


def material_usda(mat, ramp=False, checker=False, to_sun=(0, 1, 0), partial=False):
    """partial: a texture not painted yet falls back to the checker (work-in-progress looks only)."""
    if mat == "Blocker":  # the off-frame window wall: plain, never seen by the camera
        body = shader(mat, "Out", "principled_bsdf", {"base_color": (0.3, 0.27, 0.24)})
        body = body[:-len("        }")] + "            token outputs:BSDF\n        }"
        return (f'    def Material "{mat}"\n    {{\n'
                f'        token outputs:cycles:surface.connect = </Looks/{mat}/Out.outputs:BSDF>\n'
                + body + "\n    }\n")
    stem = "_checker" if checker or (partial and not os.path.exists(tex_path(mat.lower()))) else mat.lower()
    nodes = [image(mat, "Albedo", tex_path(stem), raw=False)]
    if mat == "Background":
        nodes.append(shader(mat, "Out", "emission", {"strength": 1.0}, [("color", "Albedo.color")]))
    elif ramp:
        nodes += [shader(mat, "Geo", "geometry"),
                  # start the shadow ray 0.05 cm off the surface, or it hits its own triangle
                  shader(mat, "Lift", "vector_math", {"math_type": "multiply_add",
                                                      "vector2": Vec((0.05, 0.05, 0.05))},
                         [("vector1", "Geo.normal"), ("vector3", "Geo.position")]),
                  # raycast.direction is a normal-type socket: left unconnected, Cycles silently
                  # feeds it the surface normal, so the sun direction must arrive through a node
                  shader(mat, "SunDir", "vector_math", {"math_type": "normalize", "vector1": Vec(to_sun)}),
                  shader(mat, "Ray", "raycast", {"length": 2000.0},
                         [("position", "Lift.vector"), ("direction", "SunDir.vector")]),
                  shader(mat, "NdotL", "vector_math", {"math_type": "dot_product", "vector2": Vec(to_sun)},
                         [("vector1", "Geo.normal")]),
                  shader(mat, "Open", "math", {"math_type": "subtract", "value1": 1.0},
                         [("value2", "Ray.is_hit")]),
                  shader(mat, "Lit", "math", {"math_type": "multiply", "use_clamp": True},
                         [("value1", "NdotL.value"), ("value2", "Open.value")]),
                  shader(mat, "Ramp", "rgb_ramp", {"ramp": RAMP, "ramp_alpha": [1.0] * len(RAMP),
                                                   "interpolate": False}, [("fac", "Lit.value")]),
                  shader(mat, "Tint", "mix_color", {"blend_type": "multiply", "fac": 1.0},
                         [("a", "Albedo.color"), ("b", "Ramp.color")]),
                  shader(mat, "Debug", "combine_xyz", {}, [("x", "NdotL.value"), ("y", "Ray.is_hit")]),
                  shader(mat, "Out", "emission", {"strength": 1.0},
                         [("color", "Debug.vector" if os.environ.get("RAMP_DEBUG") else "Tint.result")])]
    else:
        spec = SURFACE[mat]
        links = [("base_color", "Albedo.color")]
        if os.path.exists(tex_path(f"{stem}_normal")):
            raise SystemExit(f"{stem}_normal.png: tangent-space normal maps are silently ignored by "
                             "Cycles' Hydra delegate (it makes no tangents); paint a _height.png instead")
        for kind, socket in [("rough", "roughness"), ("height", None)]:
            f = tex_path(f"{stem}_{kind}")
            if checker or not os.path.exists(f):
                continue
            nodes.append(image(mat, kind.capitalize(), f, raw=True))
            if socket:
                links.append((socket, f"{kind.capitalize()}.color"))
        if any('"Height"' in n for n in nodes):
            s, d = spec["bump"]
            nodes.append(shader(mat, "Bump", "bump", {"strength": s, "distance": d},
                                [("height", "Height.color")]))
            links.append(("normal", "Bump.normal"))
        nodes.append(shader(mat, "Out", "principled_bsdf", spec["bsdf"], links))
    out = "Out.Emission" if (mat == "Background" or ramp) else "Out.BSDF"
    n, o = out.split(".")
    used = set(re.findall(r"/(\w+)\.outputs:(\w+)>", "\n".join(nodes))) | {(n, o)}
    for i, text in enumerate(nodes):  # declare every output something connects to
        name = text.split('"')[1]
        decl = [f"            token outputs:{oo}\n" for nn, oo in sorted(used) if nn == name]
        nodes[i] = text[:-len("        }")] + "".join(decl) + "        }"
    return (f'    def Material "{mat}"\n    {{\n'
            f'        token outputs:cycles:surface.connect = </Looks/{mat}/{n}.outputs:{o}>\n'
            + "\n".join(nodes) + "\n    }\n")
