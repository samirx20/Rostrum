"""The film's notes, collected once for run_script `look` (script_look), render_export and render_video, as shared
notes (rostrum_core.mcp.faults: {id, what, when}), only when the call asks for them (`notes: true`).

The rows are review's: the document's facts (review.doc_faults), subjects cut by the frame edge (edge_cut.scan), and
the picture checks the caller already has (look_empty: the look's tiny samples, or the finished mp4's quiet stretches).
A note's id is `kind:layer` (or `kind@seconds` when no layer is named), stable across re-runs of the same scene. A note
is what was measured, never an instruction and never a reason to hold a file back: Rostrum never refuses or changes an
agent's work (Sam, 2026-10-29); anything in a video can be right when it is meant."""
from __future__ import annotations

from rostrum_core.mcp.faults import note

from . import edge_cut, look_empty, review

FILMS = ("mp4", "prores4444", "webm", "gif")       # the formats a film is exported in: their export can carry notes
NOT_NOTED = ("empty_edge",)                          # a blank second at the very start or end: an opening / closing fade
PASSING = ("edge_cut", "rig_cut")      # a subject cut by the edge is noted only when it stays cut ...
PASS_S = 2.0                           # ... this long or more (walking in or out of the picture takes about a second)
SUBJECTS = ("group", "image", "video", "rig")   # ... and is a card, a picture, a clip or a character: a plain shape, path or
                                                # drawing bleeding off the edge is scenery (Undertow r1: 39 reef shapes)


def collect(doc_data: dict, comp: dict, times: list[float], where: str, cuts: list[dict] | None = None) -> tuple[list[dict], list[dict], list[str]]:
    """The rows the document shows over `times` (review.doc_faults + subjects cut by the edge; `cuts`: edge_cut.scan
    rows the caller already has, as video.checked's), what was measured but is no fault (review.info), and notes for
    what could not be measured. Add the picture rows and rank them with review.ranked(pixels + rows, duration)."""
    found, notes = review.doc_faults(doc_data, comp, None, where)
    if cuts is None:
        rigs, more = edge_cut.rig_boxes(doc_data, comp, times)
        cuts, notes = edge_cut.scan(comp, times, rigs, look_empty.EVERY), notes + more
    return review._cuts(cuts) + found, review.info(found), notes


def noted(r: dict) -> bool:
    """A row worth a note (a subject passing through the edge, or a fade at the very start or end, is not)."""
    k = r.get("rank_kind") or r["kind"]
    if k in NOT_NOTED:
        return False
    if k not in PASSING:
        return True
    return r.get("end", 0) - r.get("start", 0) >= PASS_S - 1e-6 and r.get("type", "rig" if k == "rig_cut" else "group") in SUBJECTS


def as_notes(rows: list[dict]) -> list[dict]:
    """review.ranked rows as shared notes, most visible first."""
    return [note(f'{r["kind"]}:{r["id"]}' if r.get("id") else f'{r["kind"]}@{r.get("start", 0):g}', r["text"],
                 f'{r["start"]:g} s' if "start" in r else None) for r in rows if noted(r)]


def of_export(doc_data: dict, comp: dict, start: float, end: float, where: str, pixels=(), cuts=None) -> tuple[list[dict], list[str]]:
    """The notes of an exported stretch: the document's rows (`cuts` / `pixels` from the finished file when the export
    checked it, an mp4), ranked, those overlapping start..end. Cheap: the document only, every look_empty.EVERY s."""
    every = look_empty.EVERY
    times = [round(start + i * every, 4) for i in range(int((end - start) / every + 1e-9))]
    rows, _, said = collect(doc_data, comp, times, where, cuts)
    rows = [r for r in review.ranked(list(pixels) + rows, comp.get("duration", 5.0))
            if "start" not in r or (r["start"] < end + 1e-6 and r.get("end", r["start"]) > start - 1e-6)]
    return as_notes(rows), said
