"""A designed sound's fields (a `sound` item on a track: whoosh, click, riser, hit, subDrop). The engine's field table
(engine/src/design/mod.rs, answered by `describe` › designs) is the authority; `Engine.check_names` compares this
table with it. Each design's own fields are valid only while that design is chosen (rule of individuality): pick
"click" and the whoosh's speed curve goes, the material appears. `group` is the clip's layer name (fields.py): a
designed sound and library clips with one group name on one track are one layered sound (ops_group.py).
"""
from __future__ import annotations

from . import values as V

N = V.N
IS = lambda name, value: {"is": [name, value]}  # noqa: E731

DESIGNS = ["whoosh", "click", "riser", "hit", "subDrop"]

# name, lo, hi, importance, label, help — per design (the engine fills the defaults).
OWN = {
    "whoosh": [("dur", 0.04, 10, "primary", "Length", "The move's start to its stop (s)."),
               ("brightness", 0, 1, "primary", "Brightness", "Dark … bright."),
               ("size", 0, 1, "primary", "Size", "Small and light … big and heavy."),
               ("doppler", 0, 1, "secondary", "Doppler", "How far the pitch falls as it passes its fastest point."),
               ("tone", 0, 1, "secondary", "Whistle", "A tuned whistle riding the sweep."),
               ("air", 0, 1, "secondary", "Air", "High air at the fastest moment."),
               ("texture", 0, 1, "secondary", "Texture", "Smooth … rough (fabric / fan flutter).")],
    "click": [("pitch", 100, 12000, "primary", "Pitch", "The body's pitch (Hz)."),
              ("material", 0, 1, "primary", "Material", "Soft plastic (0) … glass (0.5) … metal (1)."),
              ("tight", 0, 1, "primary", "Tightness", "Ringing … tight and short."),
              ("body", 0, 1, "secondary", "Body", "The tuned body's level."),
              ("transient", 0, 1, "secondary", "Snap", "The first millisecond's snap."),
              ("air", 0, 1, "secondary", "Air", "A high tick of air."),
              ("bend", -1, 1, "secondary", "Bend", "Above 0 falls into the note (a knock), below 0 rises (a pop).")],
    "riser": [("dur", 0.1, 20, "primary", "Length", "It peaks at its end (s)."),
              ("pitch", 40, 2000, "secondary", "Pitch", "The tonal layer's start (Hz); it climbs two octaves."),
              ("brightness", 0, 1, "primary", "Brightness", "How high the sweep climbs."),
              ("curve", 0, 1, "primary", "Curve", "Even climb … holds back and surges at the end."),
              ("tone", 0, 1, "secondary", "Tone", "The tonal layer's level."),
              ("air", 0, 1, "secondary", "Air", "Hiss near the peak."),
              ("texture", 0, 1, "secondary", "Flutter", "An accelerating flutter.")],
    "hit": [("pitch", 25, 200, "secondary", "Pitch", "The sub thump's pitch (Hz)."),
            ("size", 0, 1, "primary", "Size", "Small knock … huge."),
            ("brightness", 0, 1, "primary", "Brightness", "The crack and the tail's brightness."),
            ("tail", 0.05, 6, "primary", "Tail", "How long it rings (s)."),
            ("drive", 0, 1, "secondary", "Drive", "Saturation.")],
    "subDrop": [("dur", 0.1, 8, "primary", "Length", "Seconds."),
                ("pitch", 25, 200, "primary", "Lands at", "Where it lands (Hz)."),
                ("drop", 0, 4, "primary", "Drop", "How far it falls (octaves)."),
                ("drive", 0, 1, "secondary", "Drive", "Saturation.")],
}
COMMON = [("volume", 0, 4, "primary", "Level", "1 = the design's own peak level."),
          ("pan", -1, 1, "secondary", "Pan", "Left … right (a whoosh's pan path overrides it)."),
          ("width", 0, 1, "secondary", "Width", "Mono … wide."),
          ("seed", 1, 999999, "deep", "Take", "Another whole number: another take of the same design.")]
LANES = {"whoosh": ["speed", "panPath"]}
REQUIRED_BY = {"whoosh": ["dur"], "riser": ["dur"]}


def _when(designs: list[str]):
    return IS("design", designs[0]) if len(designs) == 1 else {"any": [IS("design", d) for d in designs]}


def params() -> list:
    """The `sound` item's Params: design, at, common fields, then each field once, valid for the designs that have it."""
    from rostrum_core import Param
    out = [Param.choice("design", DESIGNS, group="Sound", label="Design"), V.time("at", group="Sound", help="When it "
           "starts: seconds, {\"beat\": n} or a marker (\"#logo+0.1\").")]
    out += [N(n, lo, hi, "Sound", imp=imp, label=lab, help=h, integer=n == "seed") for n, lo, hi, imp, lab, h in COMMON]
    out.append(Param.text("group", group="Sound", importance="secondary", label="Layer group", help="Clips and "
                          "designed sounds of one track with the same group name are one layered sound."))
    seen: dict[str, list] = {}
    for d, rows in OWN.items():
        for row in rows:
            seen.setdefault(row[0], [row, []])[1].append(d)
    for name, (row, designs) in seen.items():
        # One field per name; its range spans the designs that have it (each design's own range: problems()).
        _, _, _, imp, lab, h = row
        lo = min(r[1] for d in designs for r in OWN[d] if r[0] == name)
        hi = max(r[2] for d in designs for r in OWN[d] if r[0] == name)
        if name == "dur":               # a length, which may end on a time or marker as a note's can
            out.append(V.length("dur", tied=True, group="Design", importance=imp, label=lab, valid_when=_when(designs),
                                help=h + ' Or tied: {"to": "#drop"} ends it there (a riser peaks on the marker, wherever it moves).'))
            continue
        out.append(N(name, lo, hi, "Design", imp=imp, label=lab, help=h, when=_when(designs)))
    out.append(V.curve("speed", (0, 1), (0, 1), group="Motion", importance="primary", label="Speed curve",
                       valid_when=IS("design", "whoosh"), help="[[fraction of the length, speed 0 … 1], …]: the "
                       "move's speed shapes the level, the sweep and the air."))
    out.append(V.curve("panPath", (0, 1), (-1, 1), group="Motion", importance="secondary", label="Pan path",
                       valid_when=IS("design", "whoosh"), help="[[fraction, pan], …]: follows the object across."))
    return out


def problems(item: dict) -> list[str]:
    """What one field's check can't see: a value inside the field's range but outside this design's own, a design
    that needs a field it lacks."""
    d, out = item.get("design"), []
    for name, lo, hi, *_ in OWN.get(d, []):
        v = item.get(name)
        if isinstance(v, (int, float)) and not lo <= v <= hi:
            out.append(f"{item['id']}: {name}={v} is outside {lo} … {hi} for a {d}")
    out += [f"{item['id']}: a {d} needs {k}" for k in REQUIRED_BY.get(d, []) if k not in item]
    return out


KEYS = ("design", "at", *(r[0] for r in COMMON), *{r[0] for rows in OWN.values() for r in rows}, "speed", "panPath")


def differences(described: dict) -> list[str]:
    """This table against the engine's `describe` › designs (its `designs` answer); empty when they agree."""
    out = []
    theirs = described.get("designs", {})
    if sorted(theirs) != sorted(DESIGNS):
        out.append(f"designs: python {DESIGNS}, engine {sorted(theirs)}")
    common = sorted(f["name"] for f in described.get("common", []))
    if common != sorted(r[0] for r in COMMON):
        out.append(f"design common fields differ: engine {common}")
    for d, fields in theirs.items():
        ours = {r[0]: (r[1], r[2]) for r in OWN.get(d, [])}
        eng = {f["name"]: tuple(f["accepts"]) for f in fields}
        if ours != eng:
            out.append(f"design {d}: python {ours}, engine {eng}")
    return out
