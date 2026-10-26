"""`marker.carry`: tie a cut's lead-in to the cut, so moving the marker moves the build-up with it.

Why: a time written on one marker ("#tense+4.5") follows THAT marker, so when "#reveal" moves, a riser written on
"#tense" stays and the build ends before the cut. The rule, in one place:

    marker.carry {marker: "reveal", lead_in: 4}             # 4 seconds ({"beats": 8} for beats)

Every note, hit, clip and voice line of THIS song that starts from `lead_in` before the marker up to the marker
itself, and is not already timed on that marker, gets its start rewritten as "#reveal-2.5" (or "#reveal-2.5beats"
when the lead-in was given in beats). It starts at exactly the same moment, so nothing that plays changes; from then on
it follows the marker. Lengths, tied ends and ids are untouched. One operation: one undo step, in this song's
history. Run it before the marker moves (the Sound server's edit_markers does it for a marker.move that carries
`lead_in`), and AFTER the last re-run of a script that wrote those times: a script that writes the old form again
(the same agent re-running its own script) puts it back.

`stayed(root, marker, at)` is the other half: what ENDS within a beat before the marker's place and is not on
the marker, so would stay behind when it moves. The marker tools say so in their reply; nothing is moved silently.
"""
from __future__ import annotations

from rostrum_core import Param, codes
from rostrum_core.tree import walk

from . import markers, tempo
from . import values as V
from .registry import LISTS, REGISTRY
from .select_time import end_of, start_of

TIMED = ("note", "hit", "clip", "line")
EPS = 1e-6


def _lead(p, value, where):
    ok = isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0
    if isinstance(value, dict) and set(value) == {"beats"}:
        ok = isinstance(value["beats"], (int, float)) and not isinstance(value["beats"], bool) and value["beats"] > 0
    if not ok:
        V._bad(p, value, where, "must be a positive number of seconds or {\"beats\": n}", ["4", '{"beats": 8}'])
    return value


LEAD_IN = V.Value("lead_in", "number", rule=_lead, required=True, group="Marker", label="Lead-in", unit="s",
                  schema={"anyOf": [{"type": "number", "exclusiveMinimum": 0},
                                    {"type": "object", "properties": {"beats": {"type": "number", "exclusiveMinimum": 0}},
                                     "required": ["beats"]}]},
                  help='How far before the marker the build-up reaches: seconds (4) or {"beats": 8}.')


def _items(root: dict):
    return [i for i in walk(root, LISTS) if i.get("type") in TIMED and "at" in i]


def _on(item: dict, name: str) -> bool:
    got = markers.ref(item["at"])
    return got is not None and markers.key(got) == markers.key(name)


def window(root: dict, name: str, lead_in) -> list[tuple[dict, float]]:
    """[(item, start seconds)] of what starts in the lead-in window and is not on the marker yet, by time."""
    m = markers.time_of(root, name, "marker.carry")
    if isinstance(lead_in, dict):
        lo = tempo.seconds_at(root, max(0.0, tempo.beat_at(root, m) - float(lead_in["beats"])))
    else:
        lo = m - float(lead_in)
    found = [(i, start_of(root, i)) for i in _items(root) if not _on(i, name)]
    return sorted(((i, s) for i, s in found if lo - EPS <= s < m + EPS), key=lambda p: p[1])


def stayed(root: dict, name: str, at: float | None = None) -> dict[str, int]:
    """{"3 notes on strings": …} as {(track id, kind) words: count}: what ends within a beat before `at` (default:
    the marker's place) and is not on the marker."""
    m = markers.time_of(root, name, "marker.carry") if at is None else at
    lo = m - tempo.beat_seconds(root, m)
    out: dict[str, int] = {}
    for track in (t for t in root.get("tracks", [])):
        for key, word in (("notes", "note"), ("hits", "hit"), ("clips", "clip")):
            n = sum(1 for i in track.get(key, []) if not _on(i, name) and lo - EPS <= end_of(root, i) <= m + EPS
                    and start_of(root, i) < m - EPS)
            if n:
                out[f"{n} {word}{'s' * (n != 1)} on {track['id']}"] = n
    return out


def staying_words(root: dict, name: str, at: float | None = None) -> str | None:
    found = stayed(root, name, at)
    if not found:
        return None
    return (f"{', '.join(found)} end just before #{name} and stay when it moves: "
            f'pass lead_in (seconds or {{"beats": n}}) to carry them.')


@REGISTRY.operation("marker.carry", "Tie the build-up before a marker to it: everything of this song that starts within "
                    "`lead_in` (seconds, or {\"beats\": n}) before the marker, and is not on it already, is re-timed onto "
                    "the marker (\"#reveal-2.5\"). It plays at the same moment; when the marker moves, it moves too. "
                    "Run it before moving the marker (edit_markers marker.move with `lead_in` does it).",
                    label="Carry lead-in", importance="secondary", params=[Param.text("marker", label="Marker", required=True, group="Marker"), LEAD_IN])
def carry(ctx, targets, args):
    name, lead = args["marker"], args["lead_in"]
    root = ctx.doc
    if not markers.has(root, name):
        markers.time_of(root, name, "marker.carry")                 # the loud not-found error, naming the markers
    m, beats = markers.time_of(root, name), isinstance(lead, dict)
    got = window(root, name, lead)
    if not got:
        ctx.fail(codes.BAD_ARGUMENT, "lead_in", f'nothing in this song starts within {lead} before "{name}"',
                 hint="Widen lead_in, or read what is there with look_arrangement.")
    for item, start in got:
        if beats:
            off = round(tempo.beat_at(root, start) - tempo.beat_at(root, m), 5)
            to = f"#{name}" if abs(off) < EPS else f"#{name}{off:+g}beats"
        else:
            off = round(start - m, 6)
            to = f"#{name}" if abs(off) < EPS else f"#{name}{off:+g}"
        ctx.set(item["id"], "at", to)
