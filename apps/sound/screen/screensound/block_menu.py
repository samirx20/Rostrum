"""What a right-click on a clip adds to the kit's short menu (cut, copy, paste, duplicate, delete, rename …): the clip's own
actions at the pointer — Split here, Fade in / out to here, Swap… —; on notes and hits their own actions from the action
list (Quantise, Humanise, Transpose ▸; a marker's Put a sound here …: `selection_entries`); and on the Editor's empty roll space what belongs there (Add
note here, Paste here, Select all on this track, Select every C4: `roll_entries`; a track or a marker is added elsewhere).
Every entry is an existing operation (`clip.split`, `clip.set_one`) or action (swap); values "at:<what>:…" run through
`ActionSlots.runAt`. Data only, no Qt."""
from __future__ import annotations

from rostrum_gui.action_views import menu as action_menu
from rostrum_sound.doc import select_time as ST

EDGE = 0.05      # seconds from a clip's ends within which a split or a fade point makes no sense


def _row(value, label, keys="", group="clip"):
    return {"value": value, "label": label, "keys": keys, "group": group, "sub": []}


NOTE_GROUPS = ("time", "pitch", "velocity", "marker")    # the action list's groups of what notes, hits and markers do (actions.py)


def selection_entries(entries) -> list[dict]:
    """The selected notes' / hits' / marker's own actions now valid (LIST.available entries), as menu rows: Transpose's
    four fold into one row with a side menu, as everywhere; a marker's: Put a sound here, Start a bar here…."""
    rows = [r for r in action_menu(entries) if r["group"] in NOTE_GROUPS]
    rows.sort(key=lambda r: NOTE_GROUPS.index(r["group"]))         # time first (Quantise, Humanise), then Transpose ▸
    return [{**r, "group": "own"} for r in rows]                   # one block under the short menu


def roll_entries(kind, track_id, t, row, px, can_paste, key_name="") -> list[dict]:
    """Right-click on empty space in the Editor's roll at `t` seconds on `row` (a key, or a drum row's index)."""
    out = []
    if kind in ("notes", "drums"):
        out.append(_row(f"at:rolladd:{t}:{row}:{px:.6g}", "Add note here" if kind == "notes" else "Add drum hit here",
                        "", "here"))
    if can_paste:
        out.append(_row(f"at:paste:{track_id}:{t}:{px:.6g}", "Paste here", "Ctrl+V", "here"))
    out.append(_row(f"at:all:{track_id}", "Select all on this track", "", "select"))
    if kind == "notes" and key_name:
        out.append(_row(f"at:allkey:{track_id}:{row}", f"Select every {key_name}", "", "select"))
    return out


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
