"""The Sound script layer for `run_script`: Python source -> the document tree it describes.

    tempo(96); length(bar(9)); beats_per_bar(4)
    marker("drop", at=bar(5)); tempo_change(bar(5), 132); key("D minor"); section("verse", bar(1), bar(5))
    s = track("strings", sfz=r"C:\\...\\Violins.sfz", volume=0.8)      # instrument inferred from sfz= / builtIn= / kit=
    s.note("D4", at=beat(0), dur=beats(4), vel=0.7); s.chord(["D3", "A3", "F4"], at="#drop", dur=beats(2))
    d = track("drums", kit="synth"); d.hit("kick", at=beat(0)); d.hit("snare", at="#drop+0.5")
    v = track("door"); v.clip(r"C:\\...\\door.wav", at=3.0, in_=0.42, length=1.2).effect("eq", bands=[...])
    s.effect("reverb", space="hall", mix=0.3); s.automate("volume", [(0, 0.2), ("#drop", 0.9)])
    master(loudness=-16); master.effect("limiter", ceiling=-1)
    g = track("gtr", model="guitar", position=0.2); pad = track("pad", synth="saw", attack=1.2, brightness=1800)
    s.set(legato=True, articulations={"spic": r"C:\\...\\spic.sfz"}); s.note("D4", 0, 1, art="spic")
    s.note("A4", at=bar(2), dur=beats(4), dynamics=[(0, 0.6), (1, 1.0)], vibrato={"rate": 5, "depth": 20})
    s.dynamics([(0, 0.5), ("#drop", 1.2)]); s.vibrato([(0, 0), (bar(3), 0.6)], rate=5.5, depth=25)
    s.humanize(seed=1, timing=0.012, velocity=0.06); s.phrase(bar(1), bar(5), vel=[(0, 0.5), (1, 0.9)])
    f = vel_curve([(0, 0.5), (1, 0.9)], bar(1), bar(5)); s.note("D3", at=beat(2), dur=1, vel=f(beat(2)) + 0.1)

A script error is a loud BAD_ARGUMENT naming the script and line; nothing is merged.
"""
from __future__ import annotations

import sys

from rostrum_core import RostrumError, codes
from rostrum_core.merge import check_output

from . import expression as EX
from .builder import Song
from .doc import KIND, meter

SAFE_BUILTINS = {f.__name__: f for f in (range, len, min, max, abs, round, enumerate, zip, list, dict, tuple,
                                          float, int, str, sorted, sum, reversed)}
API = ["tempo(bpm)", "length(time)", "beats_per_bar(n)", "sample_rate(hz)", "track(id, **fields)",
       "marker(name, at)", "tempo_change(at, bpm, ramp=False)", "meter_change(at, beats_per_bar)", "key(key, at)", "section(name, at, end)", "import_midi(path)",
       "master(**fields)", "beat(n)", "beats(n)", "bar(n)", "vel_curve(points, start, end)"]


def scope(song: Song) -> dict:
    def bar(n):
        """The start of bar n (bar(1) is the start of the song)."""
        if n < 1:
            raise ValueError("bars count from 1")
        return {"beat": meter.bar_start(song.root, n)}

    def vel_curve(points, start, end):
        """f(time) -> the velocity a phrase curve gives at that time (for accents on top of a phrase)."""
        ph = EX.phrase(start, end, points, "vel_curve")

        return lambda t: ph.velocity(t, {**song.root, "markers": song.markers}, "vel_curve", hold=True)
    return {
        "tempo": lambda bpm: song.set(tempo=bpm),
        "length": lambda t: song.set(length=t),
        "beats_per_bar": lambda n: song.set(beatsPerBar=n),
        "sample_rate": lambda hz: song.set(sampleRate=hz),
        "track": song.track, "marker": song.marker, "master": song.master,
        "tempo_change": song.tempo_change, "meter_change": song.meter_change, "key": song.key, "section": song.section, "import_midi": song.import_midi,
        "beat": lambda n: {"beat": n}, "beats": lambda n: {"beats": n}, "bar": bar, "vel_curve": vel_curve,
    }


def _line(name) -> str:
    tb = sys.exc_info()[2]
    line = None
    while tb:
        if tb.tb_frame.f_code.co_filename == name:
            line = tb.tb_lineno
        tb = tb.tb_next
    return f'script "{name}"' + (f" line {line}" if line else "")


def run_source(source: str, name: str) -> dict:
    """Run a Sound script; the tree it makes (checked like operation arguments, ready for Document.run_script)."""
    song = Song()
    try:
        exec(compile(source, name, "exec"), {"__builtins__": SAFE_BUILTINS, **scope(song)})
        tree = song.tree()
    except RostrumError as e:
        raise e.within(_line(name)) from e
    except Exception as e:
        raise RostrumError(codes.BAD_ARGUMENT, _line(name), "the script", f"failed: {type(e).__name__}: {e}",
                           API) from e
    check_output(KIND, tree, f"script {name}")
    problems = KIND.check(tree)
    if problems:
        raise RostrumError(codes.CHECK_FAILED, f'script "{name}"', "the song", "; ".join(problems))
    return tree
