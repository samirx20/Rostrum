"""The selection tests and calls of the voice and clean-up actions (actions.py names them): take arrows, Add line at
the playhead, and the Before / After switch of a cleaned clip. Each is one operation (`line.set`, `clip.set`), so an
agent has the same doors and each is one undo step. No Qt."""
from __future__ import annotations

from rostrum_sound import cleanup
from rostrum_sound.doc import media

from . import action_calls as C
from . import voice_takes


def _line(f, i):
    track = f.doc.item(f.doc.parent_of(i)[0])
    return track, f.doc.item(i)


def take_valid(step):
    """Earlier / Later take: every selected line has a made take that far from its current one."""
    return lambda f: f.one == "line" and all(voice_takes.neighbour(*_line(f, i), step) is not None for i in f.ids)


def take_calls(step):
    return lambda f: [C.call("line.set", [i], seed=voice_takes.neighbour(*_line(f, i), step)) for i in f.ids]


def speak_calls(f):
    """Speak again: a fresh take of each selected line (one past its newest)."""
    return [C.call("line.set", [i], seed=voice_takes.fresh_seed(*_line(f, i))) for i in f.ids]


def voice_track(f) -> bool:
    return f.one == "track" and f.count == 1 and f.items[0].get("instrument") == "voice"


def _cleaned(f):
    return bool(f.ids) and all(it["type"] == "clip" and cleanup.recipe_of(it) for it in f.items)


def ba_valid(f) -> bool:
    """Before / After: clips with a clean-up set; "After" only once the cleaned take is made (never silent)."""
    return _cleaned(f) and (not all(it.get("useCleaned", True) is False for it in f.items)
                            or all(cleanup.cached(media.file(it["media"]), cleanup.recipe_of(it)) for it in f.items))


def ba_label(f) -> str:
    return "Hear the cleaned take" if all(it.get("useCleaned", True) is False for it in f.items) else "Hear the original"


def ba_calls(f):
    after = all(it.get("useCleaned", True) is False for it in f.items)     # now hearing the original: go to After
    return [C.call("clip.set", f.ids, useCleaned=after)]
