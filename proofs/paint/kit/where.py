"""Where: "what is here" (`what`) and "did my stroke land" (`landed`). Both return readable text.

Reads the document only through the INTERFACE.md methods. Fields INTERFACE.md leaves open (layer list, mask arrays)
are looked up in a few likely spellings by the helpers at the top, so a rename in doc.py is a one-place fix.
"""
import numpy as np

from see import canvas_size


# ---- looking things up on the doc (the only place that guesses names) ------------------------------------------------
def layer_names(doc):
    """Layer names, bottom first."""
    ls = getattr(doc, "layers", None)
    if callable(ls):
        ls = ls()
    if isinstance(ls, dict):
        return list(ls.keys())
    out = []
    for l in ls or []:
        out.append(l if isinstance(l, str) else (l.get("name") if isinstance(l, dict) else l.name))
    if not out:
        raise RuntimeError("cannot list the document's layers (doc.layers)")
    return out


def layer_props(doc, name):
    """dict(mode, opacity, visible, locked) as far as the doc says; missing ones are left out."""
    ls = getattr(doc, "layers", None)
    ls = ls() if callable(ls) else ls
    o = ls[name] if isinstance(ls, dict) else next((l for l in ls if (l if isinstance(l, str) else
                                                                     (l.get("name") if isinstance(l, dict) else l.name)) == name), None)
    if o is None or isinstance(o, str):
        return {}
    get = (lambda k: o.get(k)) if isinstance(o, dict) else (lambda k: getattr(o, k, None))
    return {k: get(k) for k in ("mode", "opacity", "visible", "locked") if get(k) is not None}


def mask_names(doc):
    ms = getattr(doc, "masks", None)
    ms = ms() if callable(ms) else ms
    if isinstance(ms, dict):
        return list(ms.keys())
    return [m if isinstance(m, str) else getattr(m, "name", str(m)) for m in (ms or [])]


def mask_array(doc, name):
    """HxW float 0..1 for a mask name (a leading '!' means inverted), or None if the doc cannot give it."""
    inv = name.startswith("!")
    base = name[1:] if inv else name
    a = None
    for attr in ("mask_array", "mask_pixels", "mask_alpha"):
        f = getattr(doc, attr, None)
        if callable(f):
            a = f(base)
            break
    if a is None:
        ms = getattr(doc, "masks", None)
        m = ms.get(base) if isinstance(ms, dict) else None
        for attr in ("array", "alpha", "pixels", "render"):
            f = getattr(m, attr, None)
            if f is not None:
                a = f() if callable(f) else f
                break
    if a is None:
        return None
    a = np.asarray(a, np.float32)
    return 1 - a if inv else a


def _hex(c):
    c = np.clip(np.asarray(c[:3], np.float32), 0, 1)
    return "#%02x%02x%02x" % tuple(int(v * 255 + 0.5) for v in c)


def _batch_label(doc, batch):
    for e in doc.history():
        if e["batch"] == batch:
            return f"batch #{batch} '{e['label']}' by {e.get('author', '?')}"
    return f"batch #{batch}"


# ---- what x y --------------------------------------------------------------------------------------------------------
def what(doc, x, y):
    w, h = canvas_size(doc)
    if not (0 <= x < w and 0 <= y < h):
        raise ValueError(f"point ({x}, {y}) is outside the {w}x{h} canvas")
    comp = np.asarray(doc.composite(), np.float32)[y, x]
    lines = [f"pixel ({x}, {y}) on a {w}x{h} canvas",
             f"  composite colour: {_hex(comp)}  rgb {tuple(round(float(v), 3) for v in comp)}"]
    top = None
    names = layer_names(doc)
    rows = []
    for n in names:
        px = np.asarray(doc.layer_pixels(n), np.float32)[y, x]
        p = layer_props(doc, n)
        rows.append((n, px, p))
        if px[3] > 0.01 and p.get("visible", True):
            top = n
    lines.append("  layers (top first):")
    for n, px, p in reversed(rows):
        props = " ".join(f"{k}={v}" for k, v in p.items())
        mark = "  <- top painted layer" if n == top else ""
        lines.append(f"    {n:<14} colour {_hex(px)} alpha {px[3]:.2f}  {props}{mark}")
    if top is None:
        lines.append("  no layer has paint here")
    sid = doc.top_stroke_at(x, y)
    if sid is None:
        lines.append("  top stroke: none (nothing painted here, or only fills / gradients)")
    else:
        info = doc.stroke_info(sid)
        lines.append(f"  top stroke: id {sid} on layer '{info.get('layer')}', brush {info.get('brush')}, "
                     f"{_batch_label(doc, info.get('batch'))}")
    inside, outside, unknown = [], [], []
    for n in mask_names(doc):
        a = mask_array(doc, n)
        if a is None:
            unknown.append(n)
        elif a[y, x] > 0.5:
            inside.append(f"{n} ({a[y, x]:.2f})")
        else:
            outside.append(n)
    lines.append("  inside masks: " + (", ".join(inside) if inside else "none"))
    if outside:
        lines.append("  outside masks: " + ", ".join(outside))
    if unknown:
        lines.append("  masks I cannot read: " + ", ".join(unknown))
    return "\n".join(lines)


# ---- landed <stroke_id> ----------------------------------------------------------------------------------------------
def _bilinear(a, xs, ys):
    h, w = a.shape
    xs = np.clip(xs, 0, w - 1.001)
    ys = np.clip(ys, 0, h - 1.001)
    x0, y0 = xs.astype(int), ys.astype(int)
    fx, fy = xs - x0, ys - y0
    return (a[y0, x0] * (1 - fx) * (1 - fy) + a[y0, x0 + 1] * fx * (1 - fy)
            + a[y0 + 1, x0] * (1 - fx) * fy + a[y0 + 1, x0 + 1] * fx * fy)


def resample_path(pts, step):
    """Points along the polyline every `step` px, with unit tangents. Returns (xy Nx2, tangent Nx2, length)."""
    p = np.asarray(pts, np.float64)[:, :2]
    if len(p) == 1:
        return p, np.array([[1.0, 0.0]]), 0.0
    seg = np.hypot(*np.diff(p, axis=0).T)
    keep = np.concatenate([[True], seg > 1e-9])
    p, seg = p[keep], seg[seg > 1e-9]
    cum = np.concatenate([[0], np.cumsum(seg)])
    total = float(cum[-1])
    t = np.linspace(0, total, max(2, int(total / step) + 1))
    xy = np.stack([np.interp(t, cum, p[:, 0]), np.interp(t, cum, p[:, 1])], axis=1)
    i = np.clip(np.searchsorted(cum, t, side="right") - 1, 0, len(seg) - 1)
    tan = (p[i + 1] - p[i]) / seg[i][:, None]
    return xy, tan, total


END_SHARE = 0.08  # share of the path at each end left out of "got paint": brushes taper and fray there
MAX_FACTOR = 3.0  # the max may be this many times the mean limit (corners round off) before it counts as a miss


def landed(doc, sid, path=None):
    """Did the stroke's paint land on its path? `path` overrides the recorded path (to test a shifted one).

    For samples along the path: take the stroke's coverage across the path's normal and find where its weight
    centres. The distance of that centre from the path is the miss at that sample.
    """
    try:
        info = doc.stroke_info(sid)
    except Exception as e:
        raise ValueError(f"no stroke with id {sid} in this document ({type(e).__name__})") from None
    size = float(info.get("size") or 10)
    pts = path if path is not None else info["points"]
    cov = np.asarray(doc.stroke_coverage(sid), np.float32)
    h, w = cov.shape
    if cov.sum() <= 1e-6:
        return {"verdict": f"missed: stroke {sid} laid down no paint at all", "landed": False}
    step = max(1.0, size / 4)
    xy, tan, length = resample_path(pts, step)
    nrm = np.stack([-tan[:, 1], tan[:, 0]], axis=1)
    reach = size * 1.0 + 3
    offs = np.arange(-reach, reach + 0.01, 0.5)
    sx = xy[:, 0:1] + nrm[:, 0:1] * offs[None]
    sy = xy[:, 1:2] + nrm[:, 1:2] * offs[None]
    inside_canvas = (xy[:, 0] >= 0) & (xy[:, 0] <= w - 1) & (xy[:, 1] >= 0) & (xy[:, 1] <= h - 1)
    c = _bilinear(cov, sx, sy) * ((sx >= 0) & (sx <= w - 1) & (sy >= 0) & (sy <= h - 1))
    wsum = c.sum(axis=1)
    cen = (c * offs[None]).sum(axis=1) / np.maximum(wsum, 1e-9)
    painted = wsum > 0.5 * 0.5 * 1  # about half a pixel of full coverage across the width
    mask = None
    mname = info.get("mask")
    if mname:
        mask = mask_array(doc, mname)
    in_mask = np.ones(len(xy), bool)
    if mask is not None:
        in_mask = _bilinear(mask, xy[:, 0], xy[:, 1]) > 0.5
    expected = inside_canvas & in_mask  # samples that should have received paint
    sample_len = length / max(1, len(xy) - 1) if len(xy) > 1 else 0.0
    clipped_len = float((~expected).sum()) * sample_len
    outside_share = None
    if mask is not None:
        outside_share = float((cov * (1 - mask)).sum() / cov.sum())
    use = expected & painted
    u = np.linspace(0, 1, len(xy))
    body = expected & (u >= END_SHARE) & (u <= 1 - END_SHARE)  # every brush may taper or fray its ends on purpose
    body = body if body.any() else expected
    res = {"stroke": sid, "size": size, "length": length, "samples": int(len(xy)),
           "clipped_length": clipped_len, "outside_mask_share": outside_share,
           "painted_share": float((body & painted).sum() / max(1, body.sum()))}
    if not use.any():
        res.update(verdict=f"missed: no paint near the path of stroke {sid}", landed=False, mean=None, max=None)
        return res
    d = np.abs(cen[use])
    res.update(mean=float(d.mean()), max=float(d.max()))
    tol = max(2.0, 0.10 * size)
    res.update(tolerance=tol, max_tolerance=MAX_FACTOR * tol)
    if res["painted_share"] < 0.5:
        res.update(landed=False, verdict=f"missed: only {res['painted_share'] * 100:.0f}% of the path got paint")
    elif res["mean"] > tol:
        res.update(landed=False, verdict=f"missed by {res['mean']:.1f} px on average")
    elif res["max"] > MAX_FACTOR * tol:
        res.update(landed=False, verdict=f"missed in one place by {res['max']:.1f} px")
    else:
        res.update(landed=True, verdict="landed")
    return res


def landed_text(r):
    if r.get("mean") is None:
        return r["verdict"]
    lines = [f"stroke {r['stroke']}: {r['verdict']}",
             f"  centre line vs path: mean {r['mean']:.2f} px, max {r['max']:.2f} px "
             f"(landed means mean <= {r['tolerance']:.1f} px = max(2, 10% of size {r['size']:.0f}) "
             f"and max <= {r['max_tolerance']:.1f} px = {MAX_FACTOR:g}x that; corners and frayed ends raise the max)",
             f"  path length {r['length']:.0f} px, {r['painted_share'] * 100:.0f}% of it got paint "
             f"(first and last {END_SHARE * 100:.0f}% left out), "
             f"clipped length {r['clipped_length']:.0f} px (off the canvas or outside the mask)"]
    if r["outside_mask_share"] is not None:
        lines.append(f"  paint outside the stroke's mask: {r['outside_mask_share'] * 100:.1f}% of its coverage")
    return "\n".join(lines)
