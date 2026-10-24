"""The settings grid's pairs (SPEC 8.0): Position (X | Y), Size (W | H) and the other two-axis settings (Anchor, Stretch,
Tilt, a picture fill's Offset and Drift), two number rows next to each other that share one line, each half with its small letter inside. Everything
else is one row with its own label. A pair is ONE setting: its key mark keys both halves as one change and shows
their joint state (`pair_valid`; bridge.toggleAnimate), never X alone.
The rule is data on the rows: `half` ("first" / "second") and `letter`; the first half's label becomes the pair's name.
The letter is the axis, the last word of the label ("Looks at X" -> X, "Width" -> W), never a label's first letter (a
camera's "Looks at X" showed "L", read as a box-drawing corner). An item that rides something (`ridePath`) has its
position measured from there: the Position pair then reads "Offset from path".
Two rows pair only when they sit one after the other and are the same in every way that decides whether they show
(group, importance, where they are folded, when they are valid), so a pair is never half on screen."""
from __future__ import annotations

PAIRS = {("x", "y"): "Position", ("w", "h"): "Size", ("width", "height"): "Size", ("anchorX", "anchorY"): "Anchor",
         ("scaleX", "scaleY"): "Stretch", ("tiltX", "tiltY"): "Tilt",
         ("fillOffsetX", "fillOffsetY"): "Offset", ("fillDriftX", "fillDriftY"): "Drift"}
SAME = ("group", "importance", "valid_when", "in", "type", "unit")


def pair_up(rows: list[dict]) -> list[dict]:
    """The static rows with each Position / Size pair marked (a new list; rows are copied when marked)."""
    out = list(rows)
    for i in range(len(out) - 1):
        a, b = out[i], out[i + 1]
        name = PAIRS.get((a.get("id"), b.get("id")))
        if name and a["row"] == b["row"] == "param" and a["type"] == "number" and all(a.get(k) == b.get(k) for k in SAME):
            looks = a["label"].startswith("Looks at ")       # a camera's pair says what it is: where it looks
            out[i] = {**a, "half": "first", "letter": _axis(a["label"]), "label": "Looks at" if looks else name, "partner": b["id"]}
            out[i + 1] = {**b, "half": "second", "letter": _axis(b["label"])}
    return out


def both_anim(a: str, b: str) -> str:
    """The key mark of two halves: "" (can't be animated), "still", "keyed" or "onkey"."""
    if not a or not b:
        return a or b
    if a == b:
        return a
    return "still" if "still" in (a, b) and not ({"keyed", "onkey"} & {a, b}) else "keyed"


def partner_of(rows: list[dict], name: str) -> list[str]:
    """`name` and its pair's other half, if it has one, from the static rows: the halves a key mark acts on together."""
    for r in rows:
        if r.get("half") == "first" and name in (r.get("id"), r.get("partner")):
            return [r["id"], r["partner"]]
    return [name]


def _axis(label: str) -> str:
    return label.split()[-1][:1].upper()


def pair_valid(rows: list[dict], item: dict | None = None) -> None:
    """After evaluation: a pair shows while either half does (a search for "Y" still shows X | Y), and its one key
    mark says both halves (a key at the playhead only when both have one there; animated when either is); a Position
    pair on an item riding a path is its Offset from there."""
    for a, b in zip(rows, rows[1:]):
        if a.get("half") == "first" and b.get("half") == "second":
            a["valid"] = b["valid"] = a["valid"] or b["valid"]
            a["anim"] = both_anim(a.get("anim", ""), b.get("anim", ""))
            if a["label"] in ("Position", "Looks at") and (item or {}).get("ridePath"):
                a["label"] = "Offset from path"

