"""What a curve view draws, worked out from the document (curve_view.py): one entry per curve with its samples, keys,
the picked key's handles and its value range. No Qt. The curve itself is the one reading (rostrum_core.keys.curve).
"""
from __future__ import annotations

from rostrum_core.keys import keys_of, marked
from rostrum_core.keys.curve import handles_of

# one colour per curve, in the legend's order; ten before one repeats (All curves shows many)
COLORS = ["#ff7a6b", "#f2b33d", "#4cc38a", "#4cc9e0", "#b48cff", "#ff7ac6", "#9bd35a", "#5b8cff", "#ffa25c", "#c8c8d0"]


def stretch(k0: dict, k1: dict, h: dict) -> dict:
    """The stretch from key k0 to k1 with its two handles' places in (seconds, value)."""
    dt, dv = k1["t"] - k0["t"], k1["v"] - k0["v"]
    return {"key": k0["id"], "p0": [k0["t"], k0["v"]], "p3": [k1["t"], k1["v"]],
            "h1": [k0["t"] + h["x1"] * dt, k0["v"] + h["y1"] * dv], "h2": [k0["t"] + h["x2"] * dt, k0["v"] + h["y2"] * dv]}


def value_range(samples, stretches) -> tuple[float, float]:
    """The value range a curve needs: the curve and every handle of a Bézier stretch, with some air. Each curve is fitted
    to its own range, so every curve always fills the view (a position in metres and a turn in degrees side by side)."""
    vs = [s[1] for s in samples] + [v for s in stretches for v in (s["h1"][1], s["h2"][1])]
    if not vs:
        return -1.0, 1.0
    lo, hi = min(vs), max(vs)
    pad = (hi - lo) * 0.12 or 1.0
    return lo - pad, hi + pad


def entry(view, n: int, group: dict, owner: dict, prop: str, picked: str, frozen: dict, hidden: set) -> dict:
    """One curve: id, label, group (its item's id) and groupLabel, colour, shown, selected (holds the picked key), lo..hi,
    path [[t, v] …], keys, stretches (the handles on both sides of the picked key, where its eases have them)."""
    fid, ks = f"{owner['id']}.{prop}", keys_of(owner, prop)
    samples = view.curve(owner, prop)["samples"]
    on = next((i for i, k in enumerate(ks) if k["id"] == picked), None)
    around = {on, None if on is None else on - 1} - {None, -1}
    pairs = [(ks[i], ks[i + 1], handles_of(ks[i])) for i in range(len(ks) - 1)]
    flat = [stretch(a, b, h) for a, b, h in pairs if h and a["v"] != b["v"]]
    shown = fid not in hidden
    lo, hi = frozen.get(fid) or value_range(samples, flat)
    return {"id": fid, "label": view.field_label(owner, prop, group), "group": group["id"],
            "groupLabel": view.item_label(group), "color": COLORS[n % len(COLORS)], "shown": shown,
            "selected": on is not None, "lo": lo, "hi": hi, "path": samples,
            "stretches": [stretch(a, b, h) for i, (a, b, h) in enumerate(pairs)
                          if shown and i in around and h and a["v"] != b["v"]],
            "keys": [{"id": k["id"], "t": k["t"], "v": k["v"], "sel": k["id"] == picked,
                      "marker": marked.label(k["ref"]) if "ref" in k else ""} for k in ks]}


def numbers(view, item: dict) -> list[tuple[dict, str]]:
    """[(owner, prop)] of an item's animated number fields (its parts' too, as the app says): colours have no curve."""
    return [(o, p) for o, p in view.fields_of(item) if "v" in (keys_of(o, p) or [{}])[0]]
