"""A notes or drums track's Feel on the screen (no Qt; spec workflow 5). The document keeps one `perform` field (what
agents write); a person sees the group **Feel** after the instrument's settings, in place of the one switch
"Played like a person":

    Swing · Swing on (8ths / 16ths, only while Swing is above 0)      (a drum track: these first)
    Played like a person · while on: Looseness (ms), Velocity spread
    under More: Lean, Accent, Strum, Articulation, Vibrato, Seed

Each row is a kit param row made from `perform.FIELDS` (ranges, help) with the words a person reads; which rows show is
the rows' own `valid`, worked out here from the track's values, like every other row (nothing greyed). An amount left
out of `perform` plays the instrument family's own (the engine's table): its row says "Auto" (AUTO) until a
number is set, and putting it back (double-click) removes it again. Swing plays with the switch off.
Every edit is one `track.feel {field: value}` (merges into `perform`; null = back to the family's), never
`track.set {perform}`, so a script setting swing never wipes a person's looseness. Called from inspect.py / bridge.py,
like eq_rows.py."""
from __future__ import annotations

from rostrum_core import Param
from rostrum_gui.rows import _param_row

from rostrum_sound import KIND
from rostrum_sound.doc import perform as PF

from .timeline import kind_of

FEEL = KIND.registry.get("track.feel")      # the operation every Feel edit is
AUTO = -1                     # an amount left out: the instrument's own
OWN = {AUTO: "Auto"}
AUTO_HELP = " Auto: the instrument's own amount."
G = "Feel"
FIELD = {"feelSwing": "swing", "feelSwingGrid": "swingGrid", "feelPerson": "person", "feelLooseness": "timing",
         "feelVelocity": "velocity", "feelLean": "lean", "feelAccent": "accent", "feelStrum": "strum",
         "feelArticulation": "articulation", "feelVibrato": "vibrato", "feelSeed": "seed"}


def _p(rid, kind="number", **screen):
    """A row's Param: its words and importance from `track.feel`'s own (the operation the row runs), its range from
    the perform field, and what only the screen needs (`screen`: display, words, a choice's options)."""
    f, op = PF.BY[FIELD[rid]], FEEL.param(FIELD[rid])
    base = {"label": op.label, "group": G, "importance": op.importance, "help": f.help}
    if kind == "number":
        base.update(min=f.min, max=f.max)
    if "help" not in screen and OWN[AUTO] in (screen.get("words", {}).get(AUTO), screen.get("labels", {}).get("")):
        base["help"] += AUTO_HELP           # a row that can say "Auto" says what it means
    return Param(rid, kind, **{**base, **screen})


PARAMS = {p.name: p for p in (
    _p("feelSwing", step=0.01, display="percent", default=0,
       help="Every second 8th (or 16th) comes late; 100 % is a full triplet feel. The notes stay where they are."),
    _p("feelSwingGrid", "choice", options=[0.5, 0.25], labels={0.5: "8ths", 0.25: "16ths"}, default=0.5),
    _p("feelPerson", "toggle", default=True, help="The instrument's looseness, accents and strum; its amounts show "
                                                  "under it. Off: every note exactly on time (a swing still plays)."),
    _p("feelLooseness", control="slider", words=OWN, default=AUTO),
    _p("feelVelocity", display="percent", words=OWN, default=AUTO),
    _p("feelLean", importance="deep", default=0),
    _p("feelAccent", importance="deep", display="percent", words=OWN, default=AUTO),
    _p("feelStrum", importance="deep", display="percent", words=OWN, default=AUTO),
    _p("feelArticulation", "choice", importance="deep", options=["", *PF.ARTICULATIONS], labels={"": OWN[AUTO]}, default=""),
    _p("feelVibrato", importance="deep", min=0, max=200, unit="cents", words={0: "Off"}, default=0,
       help="How far held notes waver (cents); Off: none."),
    _p("feelSeed", importance="deep", min=0, max=99999, step=1, integer=True, words=OWN, default=AUTO,
       help="Any number: a different, still repeatable, performance. Auto: the track's own."),
)}
ORDER = {"drums": ["feelSwing", "feelSwingGrid", "feelPerson", "feelLooseness", "feelVelocity"],
         "notes": ["feelPerson", "feelLooseness", "feelVelocity", "feelSwing", "feelSwingGrid"]}
DEEP = ["feelLean", "feelAccent", "feelStrum", "feelArticulation", "feelVibrato", "feelSeed"]


def values(track: dict) -> dict:
    """Each row's value from the track's `perform` (absent or true: the family's; false: exactly as written)."""
    p = track.get("perform", True)
    d = p if isinstance(p, dict) else {}
    person = p is not False and d.get("person", True) is not False
    own = AUTO if person else 0          # switched off, the family's looseness is 0
    vib = d.get("vibrato")
    return {"feelSwing": d.get("swing", 0), "feelSwingGrid": d.get("swingGrid", 0.5), "feelPerson": person,
            "feelLooseness": d.get("timing", own), "feelVelocity": d.get("velocity", own), "feelLean": d.get("lean", 0),
            "feelAccent": d.get("accent", own), "feelStrum": d.get("strum", own),
            "feelArticulation": d.get("articulation", ""),
            "feelVibrato": vib.get("depthCents", 0) if isinstance(vib, dict) else 0, "feelSeed": d.get("seed", AUTO)}


def rows(item: dict, rows_: list[dict], more_open: bool) -> list[dict]:
    """The track's rows with the one Played-like-a-person switch replaced by the Feel group (the deep ones behind More)."""
    at = next((i for i, r in enumerate(rows_) if r["id"] == "perform" and r["row"] == "param"), None)
    if item.get("type") != "track" or at is None:
        return rows_
    base, v = rows_[at], values(item)
    ok = bool(base["holds"])
    shows = {"feelSwingGrid": v["feelSwing"] > 0, "feelLooseness": v["feelPerson"], "feelVelocity": v["feelPerson"]}

    def row(rid, deep=False):
        holds = ok and shows.get(rid, True)
        return {**base, **_param_row(PARAMS[rid]), "value": v[rid], "anim": "", "expr": "", "holds": holds,
                "valid": holds and (more_open or not deep), "valid_when": {}}

    order = ORDER["drums" if kind_of(item) == "drums" else "notes"]
    group = [{"row": "group", "id": "group:" + G, "label": G, "members": order, "value": None, "anim": "", "expr": "",
              "holds": ok, "valid": base["valid"]}]
    rest = rows_[:at] + rows_[at + 1:]                   # the group goes after the Instrument group's last row
    end = next((i for i in range(at, len(rest)) if rest[i]["row"] in ("group", "more")), len(rest))
    out = rest[:end] + group + [row(r) for r in order] + rest[end:]
    deep = [row(r, True) for r in DEEP]
    m = next((i for i, r in enumerate(out) if r["row"] == "more"), None)
    if m is None:
        return out + [{"row": "more", "id": "more", "label": "More", "members": DEEP, "value": None, "anim": "",
                       "expr": "", "holds": ok, "valid": ok}] + deep
    more = out[m]
    out[m] = {**more, "members": [*more["members"], *DEEP], "holds": more["holds"] or ok, "valid": more["holds"] or ok}
    return out[:m + 1] + deep + out[m + 1:]


def call(item: dict, param: str, value) -> dict | None:
    """The one `track.feel` an edit of a Feel row makes, or None for another row. AUTO (and Swing 0, Lean 0, Vibrato
    Off) removes the value: null, back to the family's."""
    f = FIELD.get(param)
    if f is None or item.get("type") != "track":
        return None
    if f == "person":
        v = bool(value)
    elif f == "articulation":
        v = value or None
    elif f == "swingGrid":
        v = float(value)
    elif f == "vibrato":
        old = (item.get("perform") or {}).get("vibrato") if isinstance(item.get("perform"), dict) else None
        v = {**(old if isinstance(old, dict) else {"rateHz": 5.5}), "depthCents": round(float(value), 2)} if value > 0 else None
    elif f == "seed":
        v = int(round(value)) if value >= 0 else None
    elif f in ("swing", "lean"):             # 0 is the family's own already
        v = round(float(value), 4) if value != 0 else None
    else:                                    # timing, velocity, accent, strum: 0 is a choice (none), AUTO the family's
        v = round(float(value), 4) if value >= 0 else None
    return {"op": "track.feel", "target": [item["id"]], "args": {f: v}}
