"""A PDF shading (axial = type 2, radial = type 3) → the values of 2D's gradient effect (fields.py "gradient": linear or
radial, from / middle / to colour, angle, centre). The colour function (exponential, stitching, sampled, or one per
component) is sampled, never copied, so any of them maps. 2D's gradient takes three colours at most: a function with more
bends is approximated and the report says so. Anything else (meshes, function-based, PostScript functions) → None + report."""
from __future__ import annotations

import math

TOL = 10.0                       # most a channel may be off (of 255) before the report says "approximated"


class Unsupported(Exception):
    pass


def _fn(f, x: float) -> list[float]:
    f = f.get_object()
    if isinstance(f, list):
        return [v for g in f for v in _fn(g, x)]
    kind = f.get("/FunctionType")
    d0, d1 = (float(v) for v in f.get("/Domain", [0, 1])[:2])
    x = min(max(x, d0), d1)
    if kind == 2:
        c0, c1, n = [float(v) for v in f.get("/C0", [0.0])], [float(v) for v in f.get("/C1", [1.0])], float(f.get("/N", 1))
        return [a + (x ** n) * (b - a) for a, b in zip(c0, c1)]
    if kind == 3:
        subs, bounds = f["/Functions"], [d0] + [float(v) for v in f["/Bounds"]] + [d1]
        enc = [float(v) for v in f["/Encode"]]
        i = max(k for k in range(len(subs)) if x >= bounds[k] or k == 0)
        i = min(i, len(subs) - 1)
        lo, hi = bounds[i], bounds[i + 1]
        t = enc[2 * i] if hi == lo else enc[2 * i] + (x - lo) / (hi - lo) * (enc[2 * i + 1] - enc[2 * i])
        return _fn(subs[i], t)
    if kind == 0:
        size, bps, m = int(f["/Size"][0]), int(f["/BitsPerSample"]), len(f["/Range"]) // 2
        data, mx = f.get_data(), 2 ** bps - 1
        if bps not in (8, 16):
            raise Unsupported(f"a sampled colour function with {bps} bits")
        pos = (x - d0) / ((d1 - d0) or 1) * (size - 1)
        i, fr = min(int(pos), size - 2) if size > 1 else 0, pos - int(pos)
        dec = [float(v) for v in f.get("/Decode", f["/Range"])]

        def at(k, j):
            o = (k * m + j) * bps // 8
            return int.from_bytes(data[o:o + bps // 8], "big") / mx
        return [dec[2 * j] + (at(i, j) * (1 - fr) + at(min(i + 1, size - 1), j) * fr) * (dec[2 * j + 1] - dec[2 * j]) for j in range(m)]
    raise Unsupported(f"a colour function of type {kind}")


def _rgb(cs, comps: list[float]) -> tuple[float, float, float]:
    cs = cs.get_object()
    if isinstance(cs, list):
        if cs[0] in ("/Separation", "/DeviceN"):
            return _rgb(cs[2], _fn(cs[3], comps[0]))
        if cs[0] == "/ICCBased":
            n = int(cs[1].get_object()["/N"])
            cs = {1: "/DeviceGray", 3: "/DeviceRGB", 4: "/DeviceCMYK"}[n]
        elif cs[0] in ("/CalRGB", "/CalGray"):
            cs = "/DeviceRGB" if cs[0] == "/CalRGB" else "/DeviceGray"
        else:
            raise Unsupported(f"the colour space {cs[0][1:]}")
    if cs in ("/DeviceGray", "/G") or len(comps) == 1:
        comps = [comps[0]] * 3
    elif cs in ("/DeviceCMYK", "/CMYK") or len(comps) == 4:
        c, m, y, k = comps
        comps = [(1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k)]
    return tuple(min(max(v, 0.0), 1.0) * 255 for v in comps[:3])


def _hex(c) -> str:
    return "#%02x%02x%02x" % tuple(round(v) for v in c)


def _bounds(f, d) -> list[float]:
    """The t values where a stitching function changes piece (fractions of the shading's domain)."""
    f = f.get_object()
    if isinstance(f, list) or f.get("/FunctionType") != 3:
        return []
    t0, t1 = d
    return [(float(b) - t0) / ((t1 - t0) or 1) for b in f["/Bounds"]]


def gradient(sh, to_px, box, name: str, report: list) -> dict | None:
    """Gradient-effect values for shading `sh` drawn over `box` (px: x, y, w, h). to_px maps shading space → px."""
    kind = sh.get("/ShadingType")
    try:
        if kind not in (2, 3):
            raise Unsupported(f"a shading of type {kind} ({'function-based' if kind == 1 else 'mesh'})")
        if "/Function" not in sh:
            raise Unsupported("a shading without a colour function")
        cs, d = sh["/ColorSpace"], [float(v) for v in sh.get("/Domain", [0, 1])]
        co = [float(v) for v in sh["/Coords"]]
        colour = lambda tau: _rgb(cs, _fn(sh["/Function"], d[0] + min(max(tau, 0.0), 1.0) * (d[1] - d[0])))
        if not all(sh.get("/Extend", [False, False])):
            report.append(f"'{name}': the gradient stops at its ends in the PDF; it is drawn continuing past them")
        bx, by, bw, bh = box
        if kind == 2:
            (x0, y0), (x1, y1) = to_px(co[0], co[1]), to_px(co[2], co[3])
            length = math.hypot(x1 - x0, y1 - y0)
            if length < 1e-6:
                raise Unsupported("a gradient with no length")
            ux, uy = (x1 - x0) / length, (y1 - y0) / length
            half = (bw * abs(ux) + bh * abs(uy)) / 2
            off = (bx + bw / 2 - x0) * ux + (by + bh / 2 - y0) * uy
            tau_of = lambda s: (off + (2 * s - 1) * half) / length
            s_of = lambda tau: ((tau * length - off) / half + 1) / 2 if half else 0.5
            geometry = {"style": "linear", "angle": math.degrees(math.atan2(ux, -uy)) % 360}
        else:
            (cx, cy), (ex, ey) = to_px(co[3], co[4]), to_px(co[3] + co[5], co[4])
            if math.hypot(*(a - b for a, b in zip(to_px(co[0], co[1]), (cx, cy)))) > 1.0:
                report.append(f"'{name}': the radial gradient's circles are not centred on each other; drawn centred on the outer one")
            r1, r0 = math.hypot(ex - cx, ey - cy), math.hypot(*(a - b for a, b in zip(to_px(co[0] + co[2], co[1]), to_px(co[0], co[1]))))
            rx, ry = min(cx - bx, bx + bw - cx), min(cy - by, by + bh - cy)
            rs = min(rx, ry)
            if rs <= 0 or r1 == r0:
                raise Unsupported("a radial gradient whose centre is outside its shape")
            if abs(rx - ry) > 0.05 * max(rx, ry):
                report.append(f"'{name}': the circular gradient is stretched to the shape's box (2D's radial gradient is an ellipse in the box)")
            tau_of = lambda s: (s * rs - r0) / (r1 - r0)
            s_of = lambda tau: (r0 + tau * (r1 - r0)) / rs
            geometry = {"style": "radial", "cx": (cx - bx) / bw, "cy": (cy - by) / bh}
        at = lambda s: colour(tau_of(s))
        cuts = [s for s in map(s_of, _bounds(sh["/Function"], (0.0, 1.0))) if 0.03 < s < 0.97]
        mid = cuts[0] if len(cuts) == 1 else 0.5
        c1, c2, c3 = at(0.0), at(1.0), at(mid)
        two = max(abs(at(s)[k] - (c1[k] + (c2[k] - c1[k]) * s)) for s in (i / 20 for i in range(21)) for k in range(3))
        three = max(abs(at(s)[k] - _tri(c1, c3, c2, mid, s)[k]) for s in (i / 20 for i in range(21)) for k in range(3))
        out = {**geometry, "color1": _hex(c1), "color2": _hex(c2)}
        if two > TOL:
            out.update(middle=True, color3=_hex(c3), mid=round(mid, 4))
        if min(two, three) > TOL:
            report.append(f"'{name}': the gradient has more than three colours; 2D's gradient has three, so it is approximated")
        return out
    except Unsupported as e:
        report.append(f"'{name}': {e} is not carried over (the shape is drawn without it)")
        return None


def _tri(c1, c3, c2, mid, s):
    a, b, t = (c1, c3, s / mid) if s < mid else (c3, c2, (s - mid) / (1 - mid))
    return [a[k] + (b[k] - a[k]) * t for k in range(3)]
