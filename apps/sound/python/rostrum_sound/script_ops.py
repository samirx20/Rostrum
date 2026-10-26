"""A script track runs the document's own track operations: `t.feel(swing=0.55, swingGrid=0.25)` is `track.feel`.

Any registered `track.<verb>` operation (a plugin's too) whose edits change only the track's own settings is callable
from a script, through the same operation, its argument checks and the document check: it runs on a one-track scratch
song holding the builder's track, and the track's settings come back from it. One that would change notes, other items
or the song (track.duplicate, track.remove …) refuses loudly: run it through edit_document after the script.
"""
from __future__ import annotations

from rostrum_core import RostrumError, codes
from rostrum_core import edits as E
from rostrum_core.run import plan

from .script_time import plain

_SKIP = {"set", "add"}          # the builder has its own set; a track is made with track(...)


def verbs() -> list[str]:
    """The track operations a script can call as methods (read from the registry, so a new one shows up by itself)."""
    from .doc import KIND
    return sorted(v for o in KIND.registry.ops() if o.targets and "track" in o.targets
                  and (v := o.name.partition(".")[2]) and o.name.startswith("track.") and v not in _SKIP)


def method(track, verb):
    """`track.<verb>` as a bound script method, or None when there is no such track operation."""
    if verb not in verbs():
        return None
    name = f"track.{verb}"

    def call(**args):
        from .doc import KIND, blank
        where = f"track {track.id} › {verb}"
        song = {**blank(), "tracks": [{"id": track.id, "type": "track", **track.fields}]}
        try:
            work, edits, _ = plan(KIND, song, [{"op": name, "target": [track.id], "args": plain(args)}])
        except RostrumError as e:
            raise e.within(where) from e
        if any(not isinstance(e, E.Set) or e.id != track.id or len(e.path) != 1 for e in edits):
            raise RostrumError(codes.BAD_ARGUMENT, where, name, "changes more than the track's own settings, so a "
                               "script can't call it", hint=f"Run {name} through edit_document after the script.")
        new = work["tracks"][0]
        track.fields = {k: v for k, v in new.items() if k not in ("id", "type")}
        return track
    from .doc import KIND
    call.__name__, call.__doc__ = verb, KIND.registry.get(name).summary
    return call
