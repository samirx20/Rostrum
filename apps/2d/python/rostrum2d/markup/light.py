"""Light on 2D shapes: the engine shades any element marked `data-light` as a lit, rounded form, and can cast its shadow.

How it works (all on the GPU, in the engine's filter graph): the element's own silhouette (its alpha) is blurred by
`soft` px into a height field; a shader reads that field's slope as the surface's normal and lights it with the film's
light (direction `angle`, height `elevation`): faces turned to the light get the light's colour, faces turned away
the shadow's, then only where the element is drawn (feComposite atop). `cast` px: the silhouette, offset away from the
light, blurred and tinted, is laid under the element. The light's fields can be keyed, so light moves across a still
drawing. Nothing here decides a look: every number is the agent's (defaults only fill what it left out).
"""
from __future__ import annotations

import html
import math
import re

PROGRAM = """uniform shader src; uniform float4 box; uniform float e; uniform float k; uniform float2 ldir; uniform float elev;
uniform float amount; uniform float3 hi; uniform float3 lo;
half4 main(float2 p) {
    float a = float(src.eval(p).a);
    if (a <= 0.0) { return half4(0.0); }
    float gx = float(src.eval(p + float2(e, 0.0)).a) - float(src.eval(p - float2(e, 0.0)).a);
    float gy = float(src.eval(p + float2(0.0, e)).a) - float(src.eval(p - float2(0.0, e)).a);
    float3 n = normalize(float3(-gx * k, -gy * k, 1.0));
    float3 l = normalize(float3(ldir * cos(elev), sin(elev)));
    float lit = dot(n, l) - l.z;
    float w = clamp(abs(lit) * amount, 0.0, 1.0);
    float3 c = lit > 0.0 ? hi : lo;
    return half4(float4(c * w, w));
}"""

DEFAULTS = {"angle": -45.0, "elevation": 40.0, "colour": "#fff1d6", "shadow": "#1b1430", "strength": 0.6, "soft": 24.0,
            "cast": 0.0, "castBlur": 18.0, "castColour": "#0b0716", "castOpacity": 0.45}
_TAG = re.compile(r"<([A-Za-z][\w:-]*)(\s[^<>]*?)\bdata-light(?:\s*=\s*([\"'])(.*?)\3)?([^<>]*?)(/?)>")


def _rgb(c: str) -> str:
    h = c.lstrip("#")
    h = "".join(x * 2 for x in h) if len(h) == 3 else h[:6]
    return " ".join(f"{int(h[i:i + 2], 16) / 255:.4f}" for i in (0, 2, 4))


def _own(text: str | None) -> dict:
    """data-light="soft: 40; cast: 30; strength: .8" → {soft: 40, …} (empty or "1": the film's light as it is)."""
    out = {}
    for part in (text or "").split(";"):
        k, sep, v = part.partition(":")
        if sep:
            k, v = k.strip(), v.strip()
            out[k] = v if k in ("colour", "shadow", "castColour") else float(v)
    return out


def filter_svg(fid: str, s: dict) -> str:
    """One <filter> for one element's light (its own settings over the film's light now)."""
    az = math.radians(s["angle"])
    dx, dy = math.sin(az), -math.cos(az)            # where the light comes from: 0° above, 90° from the right
    soft = max(0.5, s["soft"])
    uniforms = (f"*e {max(1.0, soft * 0.5):.3f};k {6.0:.3f};ldir {dx:.4f} {dy:.4f};elev {math.radians(s['elevation']):.4f};"
                f"amount {s['strength'] * 1.8:.4f};hi {_rgb(s['colour'])};lo {_rgb(s['shadow'])}")
    parts = [f'<feGaussianBlur in="SourceAlpha" stdDeviation="{soft:g}" result="h"/>',
             f'<feshader effect="light" in="h" result="lit" radius="{soft:g}" grow="0" uniforms="{uniforms}">'
             f'{html.escape(PROGRAM, quote=False)}</feshader>',
             '<feComposite in="lit" in2="SourceGraphic" operator="atop" result="shaded"/>']
    if s["cast"] > 0:
        parts += [f'<feOffset in="SourceAlpha" dx="{-dx * s["cast"]:.2f}" dy="{-dy * s["cast"]:.2f}" result="o"/>',
                  f'<feGaussianBlur in="o" stdDeviation="{s["castBlur"]:g}" result="ob"/>',
                  f'<feFlood flood-color="{s["castColour"]}" flood-opacity="{s["castOpacity"]:g}" result="fc"/>',
                  '<feComposite in="fc" in2="ob" operator="in" result="sh"/>',
                  '<feMerge><feMergeNode in="sh"/><feMergeNode in="shaded"/></feMerge>']
    return (f'<filter id="{fid}" x="-30%" y="-30%" width="160%" height="160%" color-interpolation-filters="sRGB">'
            + "".join(parts) + "</filter>")


def _svg_end(markup: str, start: int) -> int:
    """Just past the </svg> closing the <svg> whose start tag ends at `start` (nested <svg>s counted)."""
    depth, pos = 1, start
    for m in re.finditer(r"<(/?)svg\b[^>]*?(/?)>", markup[start:]):
        if m.group(1):
            depth -= 1
        elif not m.group(2):
            depth += 1
        if depth == 0:
            return start + m.end()
    raise ValueError("a data-light <svg> has no closing </svg>")


def apply(markup: str, light: dict) -> str:
    """Every `data-light` element of `markup` filtered by its light; the filters' <svg> put first. HTML elements only
    (a div, or an inline <svg> as a whole): the engine's shader runs on page layers, not inside one SVG picture."""
    defs, pieces, pos = [], [], 0
    while (m := _TAG.search(markup, pos)) is not None:
        fid = f"rlight{len(defs) + 1}"
        defs.append(filter_svg(fid, {**DEFAULTS, **light, **_own(m.group(4))}))
        rest = m.group(2) + m.group(5)
        style = f"filter: url(#{fid})"
        sm = re.search(r'\bstyle\s*=\s*"([^"]*)"', rest)
        own = sm.group(1).rstrip("; ") if sm else ""
        if m.group(1).lower() == "svg":
            # The engine drops a filtered <svg> picture: the filter goes on a box taking the svg's own place.
            end = _svg_end(markup, m.end())
            inner = rest[:sm.start()] + rest[sm.end():] if sm else rest
            cm = re.search(r'\sclass\s*=\s*"([^"]*)"', inner)        # its class places it too: the box takes it
            klass = f' class="{cm.group(1)}"' if cm else ""
            inner = inner[:cm.start()] + inner[cm.end():] if cm else inner
            pieces += [markup[pos:m.start()], f'<div{klass} style="{own + "; " if own else ""}{style}">',
                       f'<svg{inner} style="display:block">', markup[m.end():end], "</div>"]
            pos = end
            continue
        rest = rest[:sm.start()] + f'style="{own}; {style}"' + rest[sm.end():] if sm else rest + f' style="{style}"'
        pieces += [markup[pos:m.start()], f"<{m.group(1)}{rest}{m.group(6)}>"]
        pos = m.end()
    if not defs:
        return markup
    out = "".join(pieces) + markup[pos:]
    return ('<svg width="0" height="0" style="position:absolute;left:0;top:0"><defs>' + "".join(defs) + "</defs></svg>" + out)
