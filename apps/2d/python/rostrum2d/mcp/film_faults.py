"""The film's faults, collected once for run_script `look` (script_look) and render_export, as shared faults
(rostrum_core.mcp.faults: {id, what, when, fix}).

The rows are review's: the document's facts (review.doc_faults), subjects cut by the frame edge (edge_cut.scan), and
the picture checks the caller already has (look_empty: the look's tiny samples, or the finished mp4's quiet stretches).
A fault's id is `kind:layer` (or `kind@seconds` when no layer is named), stable across re-runs of the same scene, so a
`keep` names it. Its fix is the row's own (`fix`) or the kind's below: what to change, not "change it in the script".

A final export (FILMS of the whole composition) is gated: refused while a fault is open unless `keep` explains it by
quoting the brief (rostrum_core.mcp.brief_keep). Anything less (a png, a part of the film, lottie, motion) is a
preview and is never refused. The screen's Export button is the person's: never gated (exporting.py)."""
from __future__ import annotations

from rostrum_core.mcp.faults import fault

from . import edge_cut, look_empty, review

FILMS = ("mp4", "prores4444", "webm", "gif")       # the formats a film is delivered in; whole-film ones are finals
NOT_FAULTS = ("empty_edge",)                         # a blank second at the very start or end: an opening / closing fade
# What a client sees as broken (the judging rules' fault pass): these are faults, and they hold a final back. The rest of
# review's rows (a held framing, a held pose, a crowded lock-up ...) may be meant: named as advice, never refused.
CLIENT_VISIBLE = ("empty", "sparse", "text_edge", "text_margin", "text_crossed", "text_clipped", "text_on_text", "ghost_text",
                  "pointer_on_text", "device_cut", "push_cut", "push_bars", "screen_spill", "outside", "speck", "end_small",
                  "painted_over", "edge_cut", "rig_cut")
PASSING = ("edge_cut", "rig_cut")      # a subject cut by the edge counts only when it stays cut ...
PASS_S = 2.0                           # ... this long or more (walking in or out of the picture takes about a second)

FIX = {
    "empty": "put something on screen in this stretch: bring the next layer in sooner, or end the scene earlier",
    "washed": "give the picture contrast here: a darker background or stronger colours on what shows",
    "still": "keep something moving in this stretch: a key on a layer, or a camera move (frame().fit / .cut)",
    "block": "a plain block moving on its own reads as an empty card: bring its content in with it",
    "sparse": "fill the frame here: scale the subject up, or bring the next element in sooner",
    "text_edge": "move the text inward (or make it smaller) so its whole box sits inside the frame",
    "small_text_edge": "move the text inward so it clears the frame's edge",
    "text_margin": "move the text a little inward, off the frame's edge margin",
    "ghost_text": "fade the old text to opacity 0 (or hide it) before the new one comes in",
    "beat_missing": "key the beat's layer so the move or reveal happens at the beat's time",
    "beat_wrong_time": "move the beat's keys so it happens at the time the brief gives, not before",
    "set_hidden": "bring the character in front of the set (make it after the set in its group) or move it clear",
    "rig_hidden": "bring the character in front of what hides it, or move it clear",
    "pose_held": "key a new pose (pose({...}, at=)) or an idle() inside the held stretch",
    "arms_straight": "bend the arm: pose its elbow with a turn",
    "limbs_thin": "widen the limbs (limb(..., widths=)) to match the body",
    "bare_set": "give the character a set: a background or props behind it",
    "speck": "keep the small layer hidden (opacity 0) until it grows, or start it at its full size",
    "outside": "keep the layer inside its screen: make it inside the screen's container, or shrink it",
    "screen_spill": "make the layer inside the device's screen (its container) or shrink it to fit the screen",
    "crowded": "space the lock-up's parts apart: a bigger gap= in their row / column, or move them apart",
    "text_crossed": "move the text or the layer crossing it so they no longer overlap (the row says where)",
    "text_clipped": "make the text fit its box: a smaller size, a wider box, or fewer words",
    "text_on_text": "move one text off the other, or fade the first out before the second shows",
    "pointer_on_text": "aim the pointer beside the label (tap(spot=)) or move it away after the tap",
    "end_small": "scale the end card's mark / lock-up up so it reads in the frame",
    "end_held": "end the scene sooner, or keep something moving in the last picture",
    "alike_open": "make the opening shots differ: another layout, size or background per shot",
    "framing_held": "add a camera move or a cut inside the held stretch (frame().fit / .cut)",
    "device_cut": "move or scale the device so it sits inside the frame",
    "push_cut": "ease the camera push-in so the device stays inside the frame",
    "push_bars": "ease the camera push-in so the frame stays filled",
    "edge_cut": "move or scale the subject so it sits inside the frame, or let it leave the frame fully",
    "rig_cut": "move or scale the character so it sits inside the frame, or let it leave fully",
}
OTHER = "look at it at that time (look_frame) and move, resize or re-time the layer it names"


def collect(doc_data: dict, comp: dict, times: list[float], where: str, cuts: list[dict] | None = None) -> tuple[list[dict], list[dict], list[str]]:
    """The rows the document shows over `times` (review.doc_faults + subjects cut by the edge; `cuts`: edge_cut.scan
    rows the caller already has, as video.checked's), what was measured but is no fault (review.info), and notes for
    what could not be measured. Add the picture rows and rank them with review.ranked(pixels + rows, duration)."""
    found, notes = review.doc_faults(doc_data, comp, None, where)
    if cuts is None:
        rigs, more = edge_cut.rig_boxes(doc_data, comp, times)
        cuts, notes = edge_cut.scan(comp, times, rigs, look_empty.EVERY), notes + more
    return review._cuts(cuts) + found, review.info(found), notes


def is_fault(r: dict) -> bool:
    """A row a client would see as broken (CLIENT_VISIBLE; a subject passing through the edge is not)."""
    k = r.get("rank_kind") or r["kind"]
    if k in NOT_FAULTS or k not in CLIENT_VISIBLE:
        return False
    return k not in PASSING or r.get("end", 0) - r.get("start", 0) >= PASS_S - 1e-6


def advice(rows: list[dict], limit: int = 3) -> list[str]:
    """The first rows that are not faults (may be meant), as reply lines."""
    return [f'Worth a look (not a fault, may be meant): {r["text"]}' for r in rows if not is_fault(r)
            and (r.get("rank_kind") or r["kind"]) not in NOT_FAULTS][:limit]


def as_faults(rows: list[dict]) -> list[dict]:
    """review.ranked rows that are faults (is_fault) as shared faults, most visible first."""
    out = []
    for r in rows:
        k = r.get("rank_kind") or r["kind"]
        if not is_fault(r):
            continue
        fid = f'{r["kind"]}:{r["id"]}' if r.get("id") else f'{r["kind"]}@{r.get("start", 0):g}'
        out.append(fault(fid, r["text"], r.get("fix") or FIX.get(k) or FIX.get(r["kind"]) or OTHER,
                         f'{r["start"]:g} s' if "start" in r else None))
    return out


def final(fmt: str, start: float, end: float, duration: float, single: bool = False) -> bool:
    """A final: a film format (FILMS) of the whole composition. A part (start / end), one picture, a png sequence,
    lottie or motion is a preview."""
    return fmt in FILMS and not single and start <= 1e-6 and end >= duration - 1e-6


def of_export(doc_data: dict, comp: dict, start: float, end: float, where: str, pixels=(), cuts=None) -> tuple[list[dict], list[str]]:
    """The faults of an exported stretch: the document's rows (`cuts` / `pixels` from the finished file when the export
    checked it, an mp4), ranked, those overlapping start..end. Cheap: the document only, every look_empty.EVERY s."""
    every = look_empty.EVERY
    times = [round(start + i * every, 4) for i in range(int((end - start) / every + 1e-9))]
    rows, _, notes = collect(doc_data, comp, times, where, cuts)
    rows = [r for r in review.ranked(list(pixels) + rows, comp.get("duration", 5.0))
            if "start" not in r or (r["start"] < end + 1e-6 and r.get("end", r["start"]) > start - 1e-6)]
    return as_faults(rows), notes + advice(rows)
