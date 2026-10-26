"""A text's Weight row as names (Regular, Bold, Black …) from its family's real weights (rostrum2d/fontlist.py): a
family of separate weights picks one of them; a variable family picks among the named weights in its range, and a
weight set between them (by a script or an agent) is one more choice, named by its nearest name and its number. No Qt."""
from __future__ import annotations

from rostrum2d import fields as F, fontcheck, fontlist

NAMES = {100: "Thin", 200: "Extra Light", 300: "Light", 400: "Regular", 500: "Medium", 600: "Semibold", 700: "Bold",
         800: "Extra Bold", 900: "Black", 1000: "Extra Black"}


def word(w: float) -> str:
    """"Bold"; a weight between the named ones: its nearest name and the number ("Semibold 650")."""
    near = min(NAMES, key=lambda n: abs(n - w))
    return NAMES[near] if abs(near - w) < 1e-6 else f"{NAMES[near]} {w:g}"


def _choices(fam: dict, now) -> list[float]:
    """The weights to pick from: the family's own, or the named ones a variable family covers; plus the weight now."""
    have = [float(w) for w in fam["weights"]] if not fam["variable"] else \
        [float(n) for n in NAMES if fam["range"][0] <= n <= fam["range"][1]]
    if isinstance(now, (int, float)) and float(now) not in have:
        have.append(float(now))
    return sorted(have)


def rows(rows: list[dict], item: dict | None) -> list[dict]:
    if not item or item.get("type") not in ("text", "textstyle"):
        return rows
    try:
        fam = fontlist.family(item.get("font", F.defaults("text")["font"]))
    except Exception:  # noqa: BLE001  no engine built: the plain number row
        return rows
    if not fam:
        return rows
    lacks = fontcheck.figures_the_font_lacks(item)       # Number style: only what this font can do (the one now stays)
    out = []
    for r in rows:
        if r["row"] == "param" and r["id"] == "figures" and lacks:
            r = {**r, "options": [o for o in r["options"] if o["value"] not in lacks or o["value"] == r.get("value")]}
        if r["row"] == "param" and r["id"] == "weight":
            r = {**r, "type": "choice", "options": [{"value": w, "label": word(w)} for w in _choices(fam, r.get("value"))],
                 "min": None, "max": None, "unit": ""}
        out.append(r)
    return out
