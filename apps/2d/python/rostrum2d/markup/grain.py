"""Film grain on markup: the 2D engine's grain shader (engine scene/grain.rs, the same program) on any element marked
`data-grain="amount: .3; size: 1.5"` and, with film.grain(...), on the whole frame.

The grain sits on the element's own look and only where it is drawn (its alpha); strongest in the mid-tones, as
film's. `frame` (the film's frame number now) picks a new picture each frame unless `still` is on. The engine runs
one url() filter per page layer: on an element that is already lit, the grain is added to the end of its light's
filter; an <svg> as a whole is filtered through a box taking its place (the engine drops a filtered <svg> picture).
"""
from __future__ import annotations

import html
import re

# Copied from apps/2d/engine/render/src/scene/grain.rs (noise_sksl + PROGRAM): keep the two the same.
PROGRAM = """uniform shader src; uniform float4 box; uniform float size; uniform float amount; uniform float seed; uniform float frame; uniform float colour; uniform float soft;
float h(float2 c, float k) { float3 p = fract(float3(c.xyx) * 0.1031 + k * 0.1373); p += dot(p, p.yzx + 33.33); return fract((p.x + p.y) * p.z); }
float slope(float2 i, float2 f, float k) { float a = h(i, k) * 6.2831853; return dot(float2(cos(a), sin(a)), f); }
float gn(float2 q, float k) {
    float2 i = floor(q); float2 f = fract(q); float2 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
    return mix(mix(slope(i, f, k), slope(i + float2(1.0, 0.0), f - float2(1.0, 0.0), k), u.x),
               mix(slope(i + float2(0.0, 1.0), f - float2(0.0, 1.0), k), slope(i + float2(1.0, 1.0), f - float2(1.0, 1.0), k), u.x), u.y);
}
float g(float2 q, float k) { return soft < 0.5 ? h(floor(q), k) - 0.5 : 1.33 * gn(q, k); }
half4 main(float2 p) {
    float4 c = float4(src.eval(p));
    if (c.a <= 0.0) { return half4(c); }
    float2 q = (p - box.xy) / max(size, 0.5) + float2(mod(frame, 997.0) * 113.0, mod(frame, 991.0) * 71.0) + seed * 17.0;
    float n = g(q, 0.0);
    float3 d = colour > 0.5 ? float3(n, g(q, 1.0), g(q, 2.0)) : float3(n);
    float3 rgb = c.rgb / c.a;
    float l = dot(rgb, float3(0.2126, 0.7152, 0.0722));
    rgb = clamp(rgb + d * amount * (0.5 + 2.0 * l * (1.0 - l)), 0.0, 1.0);
    return half4(float4(rgb * c.a, c.a));
}"""

DEFAULTS = {"amount": 0.15, "size": 1.5, "seed": 1.0, "colour": 0.0, "smooth": 1.0, "still": 0.0}
_TAG = re.compile(r"<([A-Za-z][\w:-]*)(\s[^<>]*?)\bdata-grain(?:\s*=\s*([\"'])(.*?)\3)?([^<>]*?)(/?)>")


def own(text: str | None) -> dict:
    """data-grain="amount: .3; size: 2; still: 1" → {amount: .3, …} (empty: the defaults)."""
    out = {}
    for part in (text or "").split(";"):
        k, sep, v = part.partition(":")
        if sep:
            k = k.strip()
            if k not in DEFAULTS:
                raise ValueError(f'data-grain "{k}": the grain\'s words are {", ".join(DEFAULTS)}')
            v = v.strip().lower()
            out[k] = {"on": 1.0, "true": 1.0, "off": 0.0, "false": 0.0}.get(v) if v in ("on", "true", "off", "false") else float(v)
    return out


def primitive(s: dict, frame: int, src: str = "SourceGraphic") -> str:
    """The grain's <feshader> for settings `s` at frame number `frame`, reading `src` (a filter result)."""
    if not s["size"] > 0:
        raise ValueError(f"grain size must be above 0 px (got {s['size']})")
    f = 0 if s["still"] >= 0.5 else frame
    uniforms = (f"*size {s['size']:g};amount {s['amount']:g};seed {s['seed']:g};frame {f};"
                f"colour {int(s['colour'] >= 0.5)};soft {int(s['smooth'] >= 0.5)}")
    return (f'<feshader effect="grain" in="{src}" result="grained" radius="0" grow="0" uniforms="{uniforms}">'
            f"{html.escape(PROGRAM, quote=False)}</feshader>")


def filter_svg(fid: str, s: dict, frame: int) -> str:
    return f'<filter id="{fid}" color-interpolation-filters="sRGB">{primitive(s, frame)}</filter>'


def _svg_end(markup: str, start: int) -> int:
    from .light import _svg_end as end
    return end(markup, start)


def apply(markup: str, base: dict, frame: int) -> str:
    """Every `data-grain` element of `markup` grained (settings: DEFAULTS < `base` (film.grain now) < its own)."""
    defs, pieces, pos, extra = [], [], 0, {}
    while (m := _TAG.search(markup, pos)) is not None:
        s = {**DEFAULTS, **base, **own(m.group(4))}
        rest = m.group(2) + m.group(5)
        sm = re.search(r'\bstyle\s*=\s*"([^"]*)"', rest)
        style = sm.group(1).rstrip("; ") if sm else ""
        lit = re.search(r"filter:\s*url\(#(rlight\d+)\)", style)
        if lit:
            # Already lit: one filter per layer, so the grain goes at the end of the light's filter.
            extra.setdefault(lit.group(1), []).append(s)
            pieces += [markup[pos:m.start()], f"<{m.group(1)}{rest}{m.group(6)}>"]
            pos = m.end()
            continue
        fid = f"rgrain{len(defs) + 1}"
        defs.append(filter_svg(fid, s, frame))
        if m.group(1).lower() == "svg":
            end = _svg_end(markup, m.end())
            inner = rest[:sm.start()] + rest[sm.end():] if sm else rest
            cm = re.search(r'\sclass\s*=\s*"([^"]*)"', inner)        # its class places it: the box takes it
            klass = f' class="{cm.group(1)}"' if cm else ""
            inner = inner[:cm.start()] + inner[cm.end():] if cm else inner
            pieces += [markup[pos:m.start()], f'<div{klass} style="{style + "; " if style else ""}filter: url(#{fid})">',
                       f'<svg{inner} style="display:block">', markup[m.end():end], "</div>"]
            pos = end
            continue
        rest = (rest[:sm.start()] + f'style="{style + "; " if style else ""}filter: url(#{fid})"' + rest[sm.end():]
                if sm else rest + f' style="filter: url(#{fid})"')
        pieces += [markup[pos:m.start()], f"<{m.group(1)}{rest}{m.group(6)}>"]
        pos = m.end()
    out = "".join(pieces) + markup[pos:]
    for fid, grains in extra.items():
        def grow(f, grains=grains):
            body = f.group(1)
            for g in grains:
                body += primitive(g, frame, _last(body))
            return body + f.group(2)
        out = re.sub(rf'(<filter id="{fid}"[^>]*>.*?)(</filter>)', grow, out, count=1, flags=re.S)
    if not defs:
        return out
    return '<svg width="0" height="0" style="position:absolute;left:0;top:0"><defs>' + "".join(defs) + "</defs></svg>" + out


def _last(filter_body: str) -> str:
    """The result name of a filter's last step (the light's: `out`)."""
    names = re.findall(r'\bresult="([^"]+)"', filter_body)
    return names[-1] if names else "SourceGraphic"


def whole(markup: str, s: dict, frame: int, width: int, height: int, background: str) -> str:
    """The whole frame grained: everything in one box the stage's size, on the film's background (so grain shows on
    empty background too)."""
    fid = "rgrain-frame"
    return (f'<svg width="0" height="0" style="position:absolute;left:0;top:0"><defs>{filter_svg(fid, {**DEFAULTS, **s}, frame)}'
            f'</defs></svg><div style="position:absolute; left:0; top:0; width:{width}px; height:{height}px; '
            f'background:{background}; overflow:hidden; filter:url(#{fid})">{markup}</div>')
