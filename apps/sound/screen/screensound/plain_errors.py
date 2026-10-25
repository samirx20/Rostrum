"""A failed render as a sentence for the status line: the engine names the fault by its place in the schedule
("schedule.tracks[4].effects[0].bands: ..."); the person is told which track and which effect. The raw line stays in the log.
No Qt."""
from __future__ import annotations

import re

from rostrum_sound.doc import keys

from .inspect import EFFECT_WORDS

_AT = re.compile(r"schedule\.(tracks|buses)\[(\d+)\](?:\.effects\[(\d+)\])?[\w.\[\]]*:\s*")
_LEAD = re.compile(r"^(?:Error:\s*)?(?:render:\s*)?(?:Error:\s*)?(?:sound engine\s*›\s*)?", re.I)


def _owner(root: dict, kind: str, i: int) -> str:
    items = root.get(kind, [])
    if i < len(items) and items[i].get("name"):
        return f"“{items[i]['name']}”"
    return f"{'track' if kind == 'tracks' else 'group'} {i + 1}"


def say(line: str, root: dict | None = None) -> str:
    """`line` for a person: where it went wrong in words, then the engine's own reason."""
    root = root or {}
    text = _LEAD.sub("", line.strip(), count=1)
    r = _RANGE.search(text)
    if r and not _AT.search(text):                  # an instrument asked for a note outside its range
        return _out_of_range(root, text, *r.groups())
    m = _AT.search(text)
    if not m:
        return "Could not make the sound: " + re.sub(r"schedule\.[\w.\[\]]+", "the song", text) if line.startswith("Error: render") else line
    kind, i, fx = m.group(1), int(m.group(2)), m.group(3)
    items = root.get(kind, [])
    if fx is not None and i < len(items) and int(fx) < len(items[i].get("effects", [])):
        e = items[i]["effects"][int(fx)].get("effect", "effect")
        what = f"The {EFFECT_WORDS.get(e, str(e).replace('_', ' '))} on {_owner(root, kind, i)}"
    else:
        what = _owner(root, kind, i)
        what = what[0].upper() + what[1:]
    reason = text[m.end():].strip().rstrip(".")
    return f"{what} cannot play: {reason}. The last good sound plays until it is fixed."


_KEY = re.compile(r"\(key (\d+)\)")
_RANGE = re.compile(r"no sample for (\S+).*?plays (\S+)\s*[–-]\s*(\S+?)[.;]?$", re.S)


def say_preview(label: str, line: str) -> str:
    """A preview (the Library, the Editor's keys) that could not play, for a person: which sound and why, in words.
    An instrument asked for a note outside its range says the note and the range."""
    m = _RANGE.search(line)
    if m:
        note, lo, hi = m.groups()
        return f"No preview: this needs {note}, outside the {lo}–{hi} range of {label}."
    reason = re.sub(r"^(?:Error:\s*)?(?:audition:\s*)?(?:render_audition\s*›?\s*)?", "", line.strip(), flags=re.I)
    reason = re.sub(r"schedule\.[\w.\[\]]+:?\s*", "", reason).strip().rstrip(".")
    return f"No preview of {label}: {reason}."


def refusal(line: str, root: dict | None = None) -> dict:
    """A failed render as what the screen shows of it besides the status line (the Problems list's row, the loudness
    chip's words): `kind` ("out-of-range", else "render"), `item` (the track or group to jump to, "" when unknown),
    `message` (say()), `short` (the chip's few words)."""
    root = root or {}
    text = _LEAD.sub("", line.strip(), count=1)
    m = _AT.search(text)
    if _RANGE.search(text) and not m:
        t = _range_track(root, text)
        return {"kind": "out-of-range", "item": t["id"] if t else "", "message": say(line, root),
                "short": "Can't play: fix the notes"}
    items = root.get(m.group(1), []) if m else []
    i = int(m.group(2)) if m else -1
    return {"kind": "render", "item": items[i]["id"] if 0 <= i < len(items) else "", "message": say(line, root),
            "short": "Can't make the sound"}


def _range_track(root: dict, text: str) -> dict | None:
    """Which track: a recorded-sound track whose sound's name is in the instrument file's name (the engine names the file)
    and that has a note on the refused key. The file name alone is not enough: "strings" is in
    ".../vsco2-strings/ViolinEnsSusVib.sfz", the Violins' file."""
    file, k = text.lower(), _KEY.search(text)
    sounding = [t for t in root.get("tracks", []) if t.get("instrument") == "builtIn" and t.get("builtIn")]
    if k:
        sounding = [t for t in sounding if any(int(k.group(1)) in _midis(n) for n in t.get("notes", []))]
    found = [t for t in sounding if str(t["builtIn"]).lower() in file] or sounding
    return found[0] if len(found) == 1 else None


def _midis(note: dict) -> list[int]:
    try:
        return keys.midis(note["pitch"])
    except Exception:  # noqa: BLE001  a pitch the render would refuse on its own: not this note
        return []


def _out_of_range(root: dict, text: str, note: str, lo: str, hi: str) -> str:
    t = _range_track(root, text)
    who = f"“{t.get('name') or t['id']}”" if t else "A track"
    return (f"{who} can't play {note}: its sound plays {lo}–{hi}. Move those notes into that range or pick another "
            "sound. The last good sound plays until it is fixed.")
