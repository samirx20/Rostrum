"""The Sound script layer for `run_script`: Python source -> the document tree it describes.

    brief("A dark, muffled 4-bar piano loop at 90 bpm")                # the brief as given: a kept fault quotes it
    tempo(96); length(bar(9)); beats_per_bar(4)                        # 6/8: beats_per_bar(6); beat_unit(8)
    marker("drop", at=bar(5)); tempo_change(bar(5), 132); key("D minor"); section("verse", bar(1), bar(5))
    s = track("strings", sfz=r"C:\\...\\Violins.sfz", volume=0.8)      # instrument inferred from sfz= / builtIn= / kit=
    s.note("D4", at=beat(0), dur=beats(4), vel=0.7); s.chord(["D3", "A3", "F4"], at="#drop", dur=beats(2))
    p = track("keys", builtIn="piano"); b = track("bass", builtIn="uprightBass", perform=False)   # perform=False: every note exactly as written
    d = track("drums", kit="drums"); d.hit("kick", at=beat(0)); d.hit("snare", at="#drop+0.5")
    d.feel(swing=0.55, swingGrid=0.25)     # the document's own track.feel: any track.<op> that changes only the track's settings
    v = track("door"); v.clip(r"C:\\...\\door.wav", at=3.0, in_=0.42, length=1.2).effect("eq", bands=[...])
    s.effect("reverb", space="hall", mix=0.3); s.automate("volume", [(0, 0.2), ("#drop", 0.9)])
    master(loudness=-16); master.effect("limiter", ceiling=-1)
    g = track("gtr", model="guitar", position=0.2); pad = track("pad", synth="saw", attack=1.2, brightness=1800)
    s.set(legato=True, articulations={"spic": r"C:\\...\\spic.sfz"}); s.note("D4", 0, 1, art="spic")
    s.note("A4", at=bar(2), dur=beats(4), dynamics=[(0, 0.6), (1, 1.0)], vibrato={"rate": 5, "depth": 20})
    s.dynamics([(0, 0.5), ("#drop", 1.2)]); s.vibrato([(0, 0), (bar(3), 0.6)], rate=5.5, depth=25)
    s.humanize(seed=1, timing=0.012, velocity=0.06); s.phrase(bar(1), bar(5), vel=[(0, 0.5), (1, 0.9)])
    s.shape("vol", 0.5, 1.2, over=(bar(1), "#drop"), curve="late"); s.shape("bright", 0.2, 1, over=(bar(5), bar(9)))   # shape.py
    f = vel_curve([(0, 0.5), (1, 0.9)], bar(1), bar(5)); s.note("D3", at=beat(2), dur=1, vel=f(beat(2)) + 0.1)
    downbeat(bar(21), at=36.0); land(bar(21), at="#logo lands", ramp_from=bar(17)); seconds_of(bar(1) - beats(1))   # script_sync.py
    marker("logo lands", at=bar(21), shared=True)     # a project marker 2D follows (published by run_script)
    build_to("#hit", over=beats(8), parts=[cymbal_roll(d), crescendo(s, ["D3", "A3"])])   # script_build.py
    m = moment("hit", at=31.5); m.rest(s, before=0.4); m.stop(d, until=37.5); m.strike(p, ["C2", "G2"], vel=1, ring=4)   # script_moment.py
    ending("ring", at="#end")    # every part lands on the home chord there and rings out; "button" / "fade": script_ending.py

A script error is a loud BAD_ARGUMENT naming the script and line; nothing is merged.
"""
from __future__ import annotations

import re
import sys
import threading

from rostrum_core import RostrumError, codes
from rostrum_core.merge import check_output

from . import expression as EX
from .builder import Song, Track
from .doc import KIND, meter
from . import script_build, script_ending, script_moment, script_ops, script_scope, script_seconds, script_sync, writing
from .script_time import Beat, Beats, plain, until

_asked = threading.local()
API = ["brief(text)", "tempo(bpm)", "length(time)", "beats_per_bar(n)", "beat_unit(n)", "sample_rate(hz)", "track(id, **fields)", "bus(id, **fields)",
       "marker(name, at, shared=False)", "tempo_change(at, bpm, ramp=False)", "meter_change(at, beats_per_bar, beat_unit=4)", "key(key, at)", "section(name, at, end)", "import_midi(path)",
       "master(**fields)", "beat(n)", "beats(n)", "bar(n)", "until(time)", "vel_curve(points, start, end)",
       "t.shape(what, from_, to, over, curve)",
       *script_sync.API, *script_moment.API, *script_build.API, *script_ending.API, *writing.API]                                         # writing helpers: inspect_guide 'writing-music'


def scope(song: Song) -> dict:
    def bar(n):
        """The start of bar n (bar(1) is the start of the song)."""
        if n < 1:
            raise ValueError("bars count from 1")
        return Beat(meter.bar_start(song.root, n))

    def ring_out(on=True, soft_end=True):
        """Off: the song stops hard at its length, no ring-out fade (listen/end_check.py reads the ending). Needs the length first."""
        if song.root.get("length") is None:
            raise ValueError("ring_out() needs the song's length first: write length(...) before ring_out(False)")
        song.set(ringOut=bool(on), endFade=bool(soft_end))

    def vel_curve(points, start, end):
        """f(time) -> the velocity a phrase curve gives at that time (for accents on top of a phrase)."""
        ph = EX.phrase(start, end, points, "vel_curve")

        return lambda t: ph.velocity(t, {**song.root, "markers": song.marks()}, "vel_curve", hold=True)
    return {
        "brief": lambda words: song.set(brief=words),       # the brief's own words: a kept fault quotes them (brief.py)
        "tempo": lambda bpm: song.set(tempo=bpm),
        "length": lambda t: song.set(length=t),
        "ring_out": ring_out,
        "beats_per_bar": lambda n: song.set(beatsPerBar=n),
        "beat_unit": lambda n: song.set(beatUnit=n),
        "sample_rate": lambda hz: song.set(sampleRate=hz),
        "track": song.track, "bus": song.bus, "marker": song.marker, "master": song.master,
        "tempo_change": song.tempo_change, "meter_change": song.meter_change, "key": song.key, "section": song.section, "import_midi": song.import_midi,
        "beat": Beat, "beats": Beats, "bar": bar, "until": until, "vel_curve": vel_curve,
        **script_sync.scope(song), **script_moment.scope(song), **script_build.scope(song), **script_ending.scope(song), **writing.scope(song),
    }


def _line(name) -> str:
    tb = sys.exc_info()[2]
    line = None
    while tb:
        if tb.tb_frame.f_code.co_filename == name:
            line = tb.tb_lineno
        tb = tb.tb_next
    return f'script "{name}"' + (f" line {line}" if line else "")


_INTERNAL = {"item", "init_inserts", "insert_items"}


def _methods(cls) -> list[str]:
    """What a track can do, read from its class (so a new method shows up here by itself)."""
    own = [n for n in dir(cls) if not n.startswith("_") and n not in _INTERNAL and callable(getattr(cls, n))]
    return sorted({*own, *script_ops.verbs()})          # plus the document's track operations (t.feel(...))


def _failure(e: Exception, name: str, names: list[str]) -> RostrumError:
    """A script's Python error in plain words: where it happened and, when it helps, what would have worked."""
    where = _line(name)
    if isinstance(e, SyntaxError):
        return RostrumError(codes.BAD_ARGUMENT, f'script "{name}"' + (f" line {e.lineno}" if e.lineno else ""), "the script",
                            f"is not written correctly (Python could not read it): {e.msg}")
    if isinstance(e, NameError) and (m := re.match(r"name '(.+)' is not defined", str(e))):
        return RostrumError(codes.BAD_ARGUMENT, where, f'"{m[1]}"', "is not a name the script knows", names,
                            "A track you made is the variable you stored it in.")
    if isinstance(e, AttributeError) and (m := re.match(r"'Track' object has no attribute '(.+)'", str(e))):
        voice_hint = (" Spoken lines are not written in a script: a script can make the voice track (`track('narrator', instrument='voice', voice='ryan')`), "
                      "and the lines are added with edit_document `line.add` (text, at); inspect_guide 'voice' has the whole call."
                      if m[1] in ("line", "say", "speak", "lines", "voice_line", "words", "text") else "")
        return RostrumError(codes.BAD_ARGUMENT, where, f'track.{m[1]}', "is not something a track can do." + voice_hint, _methods(Track))
    if isinstance(e, ZeroDivisionError):
        return RostrumError(codes.BAD_ARGUMENT, where, "the script", "divides by zero")
    detail = {KeyError: f"looked for {e} and it is not there", IndexError: f"asked for a list position that is not there ({e})"}
    return RostrumError(codes.BAD_ARGUMENT, where, "the script", "stopped: " + detail.get(type(e), str(e) or "it failed without a reason"))


def run_source(source: str, name: str, doc=None) -> dict:
    """Run a Sound script; the tree it makes (checked like operation arguments, ready for Document.run_script).
    `doc`: the open document the tree merges into: its own markers (marker.add) are the script's to name too."""
    song = Song()
    _asked.markers = []
    song.known = list(doc.data.get("markers", [])) if doc is not None else []
    try:
        exec(compile(source, name, "exec"), {**script_scope.scope(), **scope(song)})
        script_sync.check(song)            # every downbeat / land still lands on the finished tempo map
        script_ending.apply(song)          # ending(...): the parts land, what runs past is trimmed, the length set
        script_moment.apply(song)          # each moment's rest / stop / choke / swell / strike, on every note written
        script_seconds.check(song)         # a script written in seconds is told a tempo change won't move it
        _asked.markers = song.shared_asked()   # marker(..., shared=True): run_script publishes these (mcp/script_shared.py)
        tree = plain(song.tree())          # the document holds plain values only
    except RostrumError as e:
        raise e.within(_line(name)) from e
    except Exception as e:
        raise _failure(e, name, sorted(scope(song))) from e
    check_output(KIND, tree, f"script {name}")
    problems = KIND.check({**tree, "markers": song.marks()})
    if problems:
        raise RostrumError(codes.CHECK_FAILED, f'script "{name}"', "the song", "; ".join(problems))
    return tree


def shared_asked() -> list[tuple[str, float]]:
    """[(name, seconds)] the last run on this thread asked to publish as project markers (marker(..., shared=True))."""
    return list(getattr(_asked, "markers", []))


run_source.wants_doc = True          # the MCP server's run_script passes the open document (rostrum_core/mcp/shared_edit.py)
