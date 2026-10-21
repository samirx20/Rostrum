"""TEMPORARY (until the Rust engine evaluates scenes itself, Team Hem H5+): one evaluated frame (scene.frame_at)
-> the page markup the archive renderer's `serve` takes. Everything is written as inline styles (Blitz reads
some properties only there). Anything this can't draw yet fails loudly instead of drawing something else.
Delete this file when the engine takes `{"scene": …}` (ENGINE_CONTRACT.md).
"""
from __future__ import annotations

import base64
import mimetypes
from functools import lru_cache
from html import escape
from pathlib import Path

FONTS = {"Roboto Flex": Path(r"C:\Users\Sam\Documents\CODE\OLD-EXPERIMENT\public\fonts\variable\RobotoFlex.ttf"),
         "Recursive": Path(r"C:\Users\Sam\Documents\CODE\OLD-EXPERIMENT\public\fonts\variable\Recursive.ttf"),
         "Inter": Path(r"C:\Users\Sam\Documents\CODE\OLD-EXPERIMENT\public\fonts\Inter-Regular.ttf")}
BLEND = {"add": "plus-lighter"}


class Unsupported(ValueError):
    pass


@lru_cache(maxsize=128)
def _data_url(path: str) -> str:
    p = Path(path)
    if not p.is_file():
        raise Unsupported(f"file not found: {path}")
    mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode("ascii")


def shell(comp: dict) -> str:
    faces = "".join(f'@font-face {{ font-family: "{n}"; src: url("{_data_url(str(p))}"); }}\n'
                    for n, p in FONTS.items() if p.is_file())
    w, h = comp["props"]["width"], comp["props"]["height"]
    return (f"<html><head><style>{faces}html, body {{ margin: 0; background: #000; }}\n"
            f"#rostrum-stage {{ position: relative; width: {w}px; height: {h}px; overflow: hidden; }}</style></head>"
            f'<body><div id="rostrum-stage"></div></body></html>')


def _gradient(e: dict) -> str:
    stops = [e["color1"]] + ([f'{e["color3"]} {e["mid"] * 100:.1f}%'] if e["middle"] else []) + [e["color2"]]
    if e["style"] == "radial":
        return f"radial-gradient(closest-side, {', '.join(stops)})"
    return f"linear-gradient({e['angle']}deg, {', '.join(stops)})"


def _transform(p: dict) -> str:
    parts = [f"translate({-p['anchorX'] * 100:.3f}%, {-p['anchorY'] * 100:.3f}%)"]
    if p["tiltX"] or p["tiltY"]:
        parts.append(f"perspective(1600px) rotateX({p['tiltX']}deg) rotateY({p['tiltY']}deg)")
    if p["rotation"]:
        parts.append(f"rotate({p['rotation']}deg)")
    sx, sy = p["scale"] * p["scaleX"], p["scale"] * p["scaleY"]
    if (sx, sy) != (1, 1):
        parts.append(f"scale({sx:.5f}, {sy:.5f})")
    return " ".join(parts)


def _content(node: dict, look: dict, caps) -> tuple[str, str]:
    """(style, inner html) of the layer's own box, for its type; `look` = gradient / glow-colour overrides."""
    p, t = node["props"], node["type"]
    grad = look.get("gradient")
    if t == "shape":
        style = f"width:{p['w']}px;height:{p['h']}px;box-sizing:border-box;"
        style += "border-radius:50%;" if p["shape"] == "ellipse" else f"border-radius:{p['radius']}px;"
        style += f"background:{look.get('color') or grad or p['fill']};"
        if p["stroke"]:
            style += f"border:{p['strokeWidth']}px solid {p['strokeColor']};"
        return style, ""
    if t == "text":
        style = (f"font-family:'{p['font']}';font-size:{p['size']}px;font-weight:{p['weight']:.0f};"
                 f"font-stretch:{p['stretch']}%;letter-spacing:{p['tracking']}em;line-height:{p['lineHeight']};"
                 f"text-align:{p['align']};font-variation-settings:'opsz' {min(144, max(8, p['size'])):.0f};")
        style += f"width:{p['boxWidth']}px;white-space:pre-wrap;" if p["boxWidth"] else "white-space:pre;"
        if look.get("color"):
            style += f"color:{look['color']};"
        elif grad:
            if "gradient-text" not in caps:
                raise Unsupported(f"{node['id']}: gradient letters need the new 2D engine build (Team Hem H5); "
                                  "this renderer would paint the whole box")
            style += f"background:{grad};-webkit-background-clip:text;background-clip:text;color:transparent;"
        else:
            style += f"color:{p['color']};"
        if p["stroke"]:
            style += f"-webkit-text-stroke:{p['strokeWidth']}px {p['strokeColor']};"
        return style, escape(p["body"])
    if t == "image":
        if grad:
            raise Unsupported(f"{node['id']}: a gradient on an image is not drawn by the temporary evaluator yet")
        fit = {"stretch": "fill"}.get(p["fit"], p["fit"])
        style = f"width:{p['w']}px;height:{p['h']}px;border-radius:{p['radius']}px;overflow:hidden;"
        return style, f'<img src="{_data_url(p["src"])}" style="width:100%;height:100%;object-fit:{fit};">' \
            if p["src"] else ""
    if t == "drawing":       # the painting kit's picture of the drawing shown at this frame (scene.frame_at)
        if grad:
            raise Unsupported(f"{node['id']}: a gradient on a drawing is not drawn by the temporary evaluator yet")
        style = f"width:{p['w']}px;height:{p['h']}px;"
        return style, f'<img src="{_data_url(p["src"])}" style="width:100%;height:100%;">' if p["src"] else ""
    if t == "group":
        style = f"width:{p['w']}px;height:{p['h']}px;" + ("overflow:hidden;" if p["clip"] else "")
        if grad:
            style += f"background:{grad};"
        return style, "".join(layer(c, caps) for c in node.get("layers", []))
    raise Unsupported(f"{node['id']}: unknown layer type {t}")


def _mask(m: dict) -> str:
    p = m["props"]
    if p["feather"] or p["invert"]:
        if p["shape"] != "ellipse":
            raise Unsupported(f"{m['id']}: a feathered or inverted rect mask is not drawn by the temporary evaluator yet")
        cx, cy, rx, ry = p["x"] + p["w"] / 2, p["y"] + p["h"] / 2, p["w"] / 2, p["h"] / 2
        inner, outer = ("transparent", "#000") if p["invert"] else ("#000", "transparent")
        soft = max(0.0, 100 - p["feather"] / max(rx, ry, 1) * 100)
        return (f"mask-image:radial-gradient({rx}px {ry}px at {cx}px {cy}px, {inner} {soft:.1f}%, {outer} 100%);"
                f"-webkit-mask-image:radial-gradient({rx}px {ry}px at {cx}px {cy}px, {inner} {soft:.1f}%, {outer} 100%);")
    if p["shape"] == "ellipse":
        return f"clip-path:ellipse({p['w'] / 2}px {p['h'] / 2}px at {p['x'] + p['w'] / 2}px {p['y'] + p['h'] / 2}px);"
    return f"clip-path:inset({p['y']}px calc(100% - {p['x'] + p['w']}px) calc(100% - {p['y'] + p['h']}px) {p['x']}px " \
           f"round {p['radius']}px);"


def _box(style: str, inner: str, full=True) -> str:
    size = "width:100%;height:100%;" if full else ""
    return f'<div style="position:absolute;left:0;top:0;{size}{style}">{inner}</div>'


def layer(node: dict, caps=frozenset()) -> str:
    p = node["props"]
    effects = node.get("effects", [])
    grad = next((_gradient(e["props"]) for e in effects if e["type"] == "gradient"), None)
    style, inner = _content(node, {"gradient": grad}, caps)
    blur = sum(e["props"]["radius"] for e in effects if e["type"] == "blur")
    filters = f"filter:blur({blur}px);" if blur else ""
    shadows = [e["props"] for e in effects if e["type"] == "shadow"]
    if shadows:
        s = shadows[0]
        rgba = f"rgba({int(s['color'][1:3], 16)},{int(s['color'][3:5], 16)},{int(s['color'][5:7], 16)},{s['strength']})"
        style += (f"text-shadow:{s['dx']}px {s['dy']}px {s['radius']}px {rgba};" if node["type"] == "text" else
                  f"box-shadow:{s['dx']}px {s['dy']}px {s['radius']}px {rgba};")
    def masked(content_style, extra=""):        # masks cut the content first; effects see the cut result
        html = _box(content_style, inner, full=False)
        for m in node.get("masks", []):
            html = _box(_mask(m), html)
        return _box(extra, html)

    body = masked(style, filters)
    for g in (e["props"] for e in effects if e["type"] == "glow"):   # a blurred copy behind, added light
        gs, _ = _content(node, {"gradient": grad, "color": None if g["ownColor"] else g["color"]}, caps)
        body = masked(gs, f"filter:blur({g['radius']}px);opacity:{min(1.0, g['strength'])};"
                          "mix-blend-mode:plus-lighter;") + body
    size = f"width:{p['w']}px;height:{p['h']}px;" if "w" in p else ""
    sizer = f'<div style="visibility:hidden;{style}">{inner}</div>' if node["type"] == "text" else ""
    return (f'<div id="{escape(node["id"])}" style="position:absolute;left:{p["x"]}px;top:{p["y"]}px;{size}'
            f'transform-origin:{p["anchorX"] * 100}% {p["anchorY"] * 100}%;transform:{_transform(p)};'
            f'opacity:{p["opacity"]};mix-blend-mode:{BLEND.get(p["blend"], p["blend"])};">{sizer}{body}</div>')


def stage(frame: dict, caps=frozenset()) -> str:
    """`caps`: what the renderer can draw beyond the archive's ("gradient-text")."""
    comp = frame["comp"]
    bg = comp["props"]["background"]
    return (f'<div style="position:absolute;left:0;top:0;width:100%;height:100%;background:{bg};"></div>'
            + "".join(layer(n, caps) for n in comp.get("layers", [])))
