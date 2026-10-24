"""A text's Weight row from its family's real weights (rostrum2d/fontlist.py): a family of separate weights (Arial:
Regular, Bold, Black) picks one of them; a variable family keeps the number, held to the weights it has. No Qt."""
from __future__ import annotations

from rostrum2d import fields as F, fontlist

NAMES = {100: "Thin", 200: "Extra Light", 300: "Light", 400: "Regular", 500: "Medium", 600: "Semibold", 700: "Bold",
         800: "Extra Bold", 900: "Black", 1000: "Extra Black"}


def word(w: float) -> str:
    """"Bold 700"; a weight between the named ones by its nearest name."""
    return f"{NAMES[min(NAMES, key=lambda n: abs(n - w))]} {w:g}"


def rows(rows: list[dict], item: dict | None) -> list[dict]:
    if not item or item.get("type") not in ("text", "textstyle"):
        return rows
    try:
        fam = fontlist.family(item.get("font", F.defaults("text")["font"]))
    except Exception:  # noqa: BLE001  no engine built: the plain number row
        return rows
    if not fam:
        return rows
    out = []
    for r in rows:
        if r["row"] == "param" and r["id"] == "weight":
            if fam["variable"]:                  # the nearest name beside the label: "Weight  Semibold"
                r = {**r, "min": fam["range"][0], "max": fam["range"][1],
                     "tag": word(r["value"]).rsplit(" ", 1)[0] if isinstance(r.get("value"), (int, float)) else ""}
            else:
                r = {**r, "type": "choice", "options": [{"value": float(w), "label": word(w)} for w in fam["weights"]],
                     "min": None, "max": None, "unit": ""}
        out.append(r)
    return out
