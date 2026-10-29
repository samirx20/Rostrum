"""A big moment written from a script: `moment(name, at)` and what happens around it.

    m = moment("hit", at=31.5)                  # the marker "hit" (the render's check reads hit / stop / drums out /
                                                #   drums back / climax / lift as asked moments) and a Moment
    m.rest(strings, basses, before=0.4)         # a breath before: nothing starts in the 0.4 s before, what rings is cut there
    m.stop(band, keys, until=37.5, short=0.2)   # the band stops: on-the-moment notes and hits play (cut to 0.2 s), what
                                                #   rings ends, nothing starts again before 37.5 s (default: the song's end)
    m.choke(drums, keys, after=0.25)            # what sounds at the moment (notes, a crash still ringing) ends 0.25 s after it
    m.strike(brass, ["C2", "G2", "C3"], vel=1.0, ring=4.0); m.strike(drums, "crash", vel=1.0, ring=1.5)
    m.swell(strings, over=4.0, low=0.5)         # velocities in the 4 s before rise from 0.5x to full into the moment

A drum hit ends by its `cut` (seconds after it is struck; the engine stops it there on every kit, fading over its last
10 ms): stop and choke write it on the hits they end, strike's `ring` on the hits it adds.

`at` is any time (seconds, bar(n), "#marker"); `at` left out uses a marker of that name already there. The actions are
kept and applied when the script ends, after every note is written, on the notes the script wrote (`apply`), in the
order written; each says what it did in the run's reply. A person's own edits to the document stay governed by the merge.
"""
from __future__ import annotations

from rostrum_core import RostrumError, codes

from . import script_moment_edit as E
from .builder import Track
from .doc import markers, times
from .script_scope import say

API = ["moment(name, at)", "m.rest(*tracks, before)", "m.stop(*tracks, until=None, short=None, release=0)",
       "m.choke(*tracks, after)", "m.strike(track, notes_or_drum, vel=None, ring=None)", "m.swell(*tracks, over, low)"]


def _secs(v, name, where, forms):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
        raise RostrumError(codes.BAD_ARGUMENT, where, f"{name}={v!r}", "is not a number of seconds (≥ 0)", forms)
    return float(v)


def _tracks(tracks, where, form):
    if not tracks or not all(isinstance(t, Track) for t in tracks):
        bad = next((t for t in tracks if not isinstance(t, Track)), None)
        raise RostrumError(codes.BAD_ARGUMENT, where, repr(bad) if tracks else "no track",
                           "is not a track: pass the tracks themselves (the variables track(...) gave)", [form])
    return list(tracks)


class Moment:
    def __init__(self, song, name, at):
        self.song, self.name, self.at, self.actions = song, name, at, []

    def _do(self, kind, tracks, **args):
        self.actions.append((kind, tracks, args))
        return self

    def rest(self, *tracks, before=None):
        """A breath before the moment: nothing starts in the `before` seconds before it; notes ringing into it end there."""
        w = f"moment {self.name} › rest"
        return self._do("rest", _tracks(tracks, w, "m.rest(strings, basses, before=0.4)"),
                        before=_secs(before, "before", w, ["before=0.4"]))

    def stop(self, *tracks, until=None, short=None, release=0):
        """The tracks stop on the moment: notes and hits on it play, what rings across it ends at the moment (+ release s),
        nothing starts again before `until` (a time; default the song's end). `short`: on-the-moment notes last that long."""
        w = f"moment {self.name} › stop"
        if until is not None and times.problem(until):
            raise RostrumError(codes.BAD_ARGUMENT, w, f"until={until!r}", times.problem(until), ["until=37.5", "until=bar(23)", 'until="#back"'])
        return self._do("stop", _tracks(tracks, w, "m.stop(drums, bass, until=26.0)"), until=until,
                        short=None if short is None else _secs(short, "short", w, ["short=0.2"]),
                        release=_secs(release, "release", w, ["release=0.05"]))

    def choke(self, *tracks, after=None):
        """Notes and drum hits sounding at the moment end `after` seconds past it (the pedal lifted, the cymbal grabbed)."""
        w = f"moment {self.name} › choke"
        return self._do("choke", _tracks(tracks, w, "m.choke(keys, after=0.25)"),
                        after=_secs(after, "after", w, ["after=0.25"]))

    def strike(self, track, what, vel=None, ring=None):
        """A layer of the hit on `track`: a note or chord held `ring` seconds, or (a kit) a drum hit / list of drums, cut
        after `ring` seconds when given (else it rings out)."""
        w = f"moment {self.name} › strike"
        _tracks([track], w, 'm.strike(brass, ["C2", "G2"], vel=1.0, ring=4.0)')
        kit = track.fields.get("instrument") == "kit"
        if not kit and ring is None:
            raise RostrumError(codes.BAD_ARGUMENT, w, f"track {track.id}", "needs how long the strike rings (ring= seconds)",
                               ['m.strike(brass, ["C2", "G2"], vel=1.0, ring=4.0)'], "A kit takes drum names: m.strike(drums, \"crash\").")
        ring = None if ring is None else _secs(ring, "ring", w, ["ring=4.0"])
        return self._do("strike", [track], what=what, vel=vel, ring=ring, kit=kit)

    def swell(self, *tracks, over=None, low=None):
        """Velocities of what starts in the `over` seconds before the moment rise from `low`x to full into it."""
        w = f"moment {self.name} › swell"
        if isinstance(low, bool) or not isinstance(low, (int, float)) or not 0 <= low <= 1:
            raise RostrumError(codes.BAD_ARGUMENT, w, f"low={low!r}", "is not a share of the velocity (0 … 1)", ["low=0.5"])
        over = _secs(over, "over", w, ["over=4.0"])
        if over <= 0:
            raise RostrumError(codes.BAD_ARGUMENT, w, "over=0", "is no time to swell over", ["over=4.0"])
        return self._do("swell", _tracks(tracks, w, "m.swell(strings, over=4.0, low=0.5)"), over=over, low=float(low))


def moment(song, name, at=None) -> Moment:
    where = f"moment {name}"
    if not isinstance(name, str) or not name.strip():
        raise RostrumError(codes.BAD_ARGUMENT, "moment", repr(name), "is not a moment name", ['moment("hit", at=31.5)'])
    if any(m.name == name for m in song.moments):
        raise RostrumError(codes.BAD_ARGUMENT, where, f'moment "{name}"', "is made twice: keep the Moment and add to it")
    if at is not None:
        song.marker(name, at)
    elif not any(markers.key(m["name"]) == markers.key(name) for m in song.marks()):
        raise RostrumError(codes.BAD_ARGUMENT, where, f'marker "{name}"', "is not there: give the moment its time",
                           [f'moment("{name}", at=31.5)', f'moment("{name}", at=bar(17))'])
    song.moments.append(Moment(song, name, at))
    return song.moments[-1]


def apply(song) -> None:
    """Every moment's actions on the notes and hits the script wrote, in the order written."""
    root = {**song.root, "markers": song.marks()}
    for m in song.moments:
        where = f"moment {m.name}"
        at = markers.time_of(root, m.name, where)
        end = times.seconds(song.root["length"], root, where) if song.root.get("length") is not None else float("inf")
        said = []
        for kind, tracks, a in m.actions:
            c, names = E.Counts(), ", ".join(t.id for t in tracks)
            for t in tracks:
                if kind == "rest":
                    E.rest(t, at, a["before"], root, where, c)
                elif kind == "stop":
                    until = end if a["until"] is None else times.seconds(a["until"], root, where)
                    E.stop(t, at, until, a["short"], a["release"], root, where, c)
                elif kind == "choke":
                    E.choke(t, at, a["after"], root, where, c)
                elif kind == "swell":
                    E.swell(t, at, a["over"], a["low"], root, where, c)
                else:
                    _strike(t, at, a, c)
            lead = {"rest": f"rest {a.get('before', 0):.2f} s", "stop": "stop", "choke": f"choke after {a.get('after', 0):.2f} s",
                    "swell": f"swell over {a.get('over', 0):.1f} s", "strike": "strike"}[kind]
            said.append(f"{lead} on {names} ({c.said()})")
        say(f"moment {m.name} at {at:.2f} s: " + "; ".join(said or ["no actions"]))


def _strike(track, at, a, counts):
    if a["kit"]:
        for drum in a["what"] if isinstance(a["what"], (list, tuple)) else [a["what"]]:
            track.hit(drum, at=round(at, 6), vel=a["vel"], cut=a["ring"])
            counts.add("hits added")
    else:
        track.note(a["what"], at=round(at, 6), dur=a["ring"], vel=a["vel"])
        counts.add("notes added", len(a["what"]) if isinstance(a["what"], (list, tuple)) else 1)


def scope(song) -> dict:
    song.moments = []
    return {"moment": lambda name, at=None: moment(song, name, at)}
