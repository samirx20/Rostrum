"""Put keyed values onto markup: an element found by its id gets an attribute, a CSS property or a transform.

Which kind a property is, by the element: inside SVG (an SVG tag) a property is an attribute (cx, d, fill,
stop-color, opacity, …); on an HTML element it is a CSS property (opacity, background, filter, left, …). A name
starting with "--" is always a CSS variable, "data-" always an attribute, "style:" forces CSS and "attr:" forces an
attribute. The transform
channels x, y, rotate, scale, scaleX, scaleY, skewX are composed in that order AFTER the element's own transform, so
in its own units: a part drawn as <g transform="translate(0 140)"> (its joint at its own 0 0) turns about that joint.
`origin` moves the pivot ("cx cy" in the element's own SVG units; any CSS transform-origin on HTML).
"""
from __future__ import annotations

import html
import re

SVG_TAGS = {"svg", "g", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "text", "tspan", "textPath",
            "use", "image", "stop", "linearGradient", "radialGradient", "clipPath", "mask", "filter", "pattern",
            "symbol", "defs", "marker"} | {f"fe{n}" for n in (
                "GaussianBlur", "DropShadow", "Offset", "ColorMatrix", "Turbulence", "DisplacementMap", "Flood",
                "Composite", "Merge", "MergeNode", "Morphology", "ComponentTransfer", "FuncA", "FuncR", "FuncG", "FuncB",
                "Image", "Blend")}
CHANNELS = ("x", "y", "rotate", "scale", "scaleX", "scaleY", "skewX", "origin")
_ATTR = re.compile(r'([:\w-]+)\s*=\s*("[^"]*"|\'[^\']*\')')


def _tag_re(ident: str) -> re.Pattern:
    return re.compile(r"<([A-Za-z][\w:-]*)(\s[^<>]*?\bid\s*=\s*([\"'])" + re.escape(ident) + r"\3[^<>]*?)(/?)>")


def _fmt(v) -> str:
    if isinstance(v, float):
        r = round(v, 3)
        return str(int(r)) if r == int(r) else f"{r:g}"
    return str(v)


def _attrs(text: str) -> list[list[str]]:
    return [[m.group(1), html.unescape(m.group(2)[1:-1])] for m in _ATTR.finditer(text)]


def _style_set(style: str, props: dict) -> str:
    parts = [p.strip() for p in style.split(";") if p.strip()]
    seen = {}
    for p in parts:
        k, _, v = p.partition(":")
        seen[k.strip()] = v.strip()
    for k, v in props.items():
        seen[k] = v
    return "; ".join(f"{k}: {v}" for k, v in seen.items())


def _svg_transform(ch: dict, own: str) -> str:
    ox, oy = (str(ch.get("origin", "0 0")).replace(",", " ").split() + ["0", "0"])[:2]
    out = []
    if "x" in ch or "y" in ch:
        out.append(f"translate({_fmt(ch.get('x', 0))} {_fmt(ch.get('y', 0))})")
    turn = [f"rotate({_fmt(ch['rotate'])})"] if "rotate" in ch else []
    s = ch.get("scale", 1)
    sx, sy = ch.get("scaleX", 1) * s, ch.get("scaleY", 1) * s
    if (sx, sy) != (1, 1):
        turn.append(f"scale({_fmt(sx)} {_fmt(sy)})")
    if "skewX" in ch:
        turn.append(f"skewX({_fmt(ch['skewX'])})")
    if turn:
        out += [f"translate({ox} {oy})", *turn, f"translate({-float(ox):g} {-float(oy):g})"]
    return " ".join(([own] if own else []) + out)


def _css_transform(ch: dict) -> str:
    out = []
    if "x" in ch or "y" in ch:
        out.append(f"translate({_fmt(ch.get('x', 0))}px, {_fmt(ch.get('y', 0))}px)")
    if "rotate" in ch:
        out.append(f"rotate({_fmt(ch['rotate'])}deg)")
    s = ch.get("scale", 1)
    sx, sy = ch.get("scaleX", 1) * s, ch.get("scaleY", 1) * s
    if (sx, sy) != (1, 1):
        out.append(f"scale({_fmt(sx)}, {_fmt(sy)})")
    if "skewX" in ch:
        out.append(f"skewX({_fmt(ch['skewX'])}deg)")
    return " ".join(out)


# CSS properties whose bare numbers have no unit (React's list, which agents write by habit); any other CSS property
# given a bare number takes px, as in React: `left: 500` is 500px, never an invalid value the page drops silently.
UNITLESS = {"opacity", "z-index", "font-weight", "line-height", "flex", "flex-grow", "flex-shrink", "order", "zoom",
            "scale", "fill-opacity", "stroke-opacity", "stop-opacity", "flood-opacity", "stroke-miterlimit",
            "animation-iteration-count", "column-count", "grid-row", "grid-column", "orphans", "widows", "tab-size",
            "aspect-ratio", "font-size-adjust"}


def _css_value(name: str, v) -> str:
    if isinstance(v, (int, float)) and not isinstance(v, bool) and not name.startswith("--") and name not in UNITLESS:
        return _fmt(v) + "px"
    return _fmt(v)


def set_props(markup: str, ident: str, props: dict, missing: list | None = None) -> str:
    """`markup` with element `ident` given `props` ({name: value}); every element with that id (ids are meant to be
    unique). An id not found is added to `missing` (the caller says so, never silently)."""
    rx = _tag_re(ident)
    found = False

    def put(m: re.Match) -> str:
        nonlocal found
        found = True
        tag, rest, close = m.group(1), m.group(2), m.group(4)
        svg = tag in SVG_TAGS
        attrs = _attrs(rest)
        named = {a[0]: a for a in attrs}
        css, ch = {}, {}
        for k, v in props.items():
            if k in CHANNELS:
                ch[k] = v
            elif k.startswith("--") or k.startswith("style:") or (not svg and not k.startswith(("attr:", "data-"))):
                name = k.removeprefix("style:")
                css[name] = _css_value(name, v)
            else:
                k = k.removeprefix("attr:")
                if k in named:
                    named[k][1] = _fmt(v)
                else:
                    attrs.append([k, _fmt(v)])
                    named[k] = attrs[-1]
        if ch:
            if svg:
                own = named["transform"][1] if "transform" in named else ""
                tr = _svg_transform(ch, own)
                if "transform" in named:
                    named["transform"][1] = tr
                else:
                    attrs.append(["transform", tr])
            else:
                css["transform"] = _css_transform(ch)
                if "origin" in ch:
                    css["transform-origin"] = str(ch["origin"])
        if css:
            if "style" in named:
                named["style"][1] = _style_set(named["style"][1], css)
            else:
                attrs.append(["style", _style_set("", css)])
        body = " ".join(f'{k}="{html.escape(str(v), quote=True)}"' for k, v in attrs)
        return f"<{tag} {body}{' /' if close else ''}>"

    out = rx.sub(put, markup)
    if not found and missing is not None:
        missing.append(ident)
    return out
