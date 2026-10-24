"""What a right-click on a clip adds to the kit's short menu (cut, copy, paste, duplicate, delete, rename …): the clip's own
actions at the pointer — Split here, Fade in / out to here, Swap… — and what a right-click on empty lane space adds: Add track.
Every entry is an existing operation (`clip.split`, `clip.set_one`) or action (swap); values "at:<what>:…" run through
`ActionSlots.runAt`. Data only, no Qt."""
from __future__ import annotations

from rostrum_sound.doc import select_time as ST

EDGE = 0.05      # seconds from a clip's ends within which a split or a fade point makes no sense


def _row(value, label, keys=""):
    return {"value": value, "label": label, "keys": keys, "group": "clip", "sub": []}


def clip_entries(doc, clip_id, t, swap_valid):
    """The clip rows for the pointer at `t` (seconds); [] for anything that is not an audio clip."""
    item = doc.item(clip_id)
    if not item or item["type"] != "clip":
        return []
    start, end = ST.start_of(doc.data, item), ST.end_of(doc.data, item)
    out = []
    if start + EDGE < t < end - EDGE:
        out.append(_row(f"at:split:{clip_id}:{round(t, 4)}", "Split here"))
        out.append(_row(f"at:fadein:{clip_id}:{round(t - start, 3)}", "Fade in to here"))
        out.append(_row(f"at:fadeout:{clip_id}:{round(end - t, 3)}", "Fade out from here"))
    if swap_valid:
        out.append(_row("swap", "Swap…", "S"))
    return out


def calls_for(what, clip_id, number):
    """The operation call of a clip row made above (what = split | fadein | fadeout)."""
    if what == "split":
        return [{"op": "clip.split", "target": [clip_id], "args": {"at": number}}], "Split here"
    key = "fadeIn" if what == "fadein" else "fadeOut"
    return [{"op": "clip.set_one", "target": [clip_id], "args": {key: number}}], "Fade in" if what == "fadein" else "Fade out"
