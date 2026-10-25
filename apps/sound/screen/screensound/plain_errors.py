"""A failed render as a sentence for the status line: the engine names the fault by its place in the schedule
("schedule.tracks[4].effects[0].bands: ..."); the person is told which track and which effect. The raw line stays in the log.
No Qt."""
from __future__ import annotations

import re

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


def _out_of_range(root: dict, text: str, note: str, lo: str, hi: str) -> str:
    """Which track: a track whose sound's name is in the instrument file's name (the engine names the file)."""
    file = text.lower()
    names = [t.get("name") or t["id"] for t in root.get("tracks", [])
             if t.get("instrument") == "builtIn" and str(t.get("builtIn", "")).lower() in file and t.get("builtIn")]
    who = f"“{names[0]}”" if len(names) == 1 else "A track"
    return (f"{who} can't play {note}: its sound plays {lo}–{hi}. Move those notes into that range or pick another "
            "sound. The last good sound plays until it is fixed.")
