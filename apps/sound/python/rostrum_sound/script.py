"""The Sound script layer for `run_script`: Python source -> the document tree it describes.

    tempo(96); length(bar(9)); beats_per_bar(4)
    marker("drop", at=bar(5))
    s = track("strings", sfz=r"C:\\...\\Violins.sfz", volume=0.8)      # instrument inferred from sfz= / builtIn= / kit=
    s.note("D4", at=beat(0), dur=beats(4), vel=0.7); s.chord(["D3", "A3", "F4"], at="#drop", dur=beats(2))
    d = track("drums", kit="synth"); d.hit("kick", at=beat(0)); d.hit("snare", at="#drop+0.5")
    v = track("door"); v.clip(r"C:\\...\\door.wav", at=3.0, in_=0.42, length=1.2).effect("eq", bands=[...])
    s.effect("reverb", space="hall", mix=0.3); s.automate("volume", [(0, 0.2), ("#drop", 0.9)])
    master(loudness=-16); master.effect("limiter", ceiling=-1)

A script error is a loud BAD_ARGUMENT naming the script and line; nothing is merged.
"""
from __future__ import annotations

import sys

from rostrum_core import RostrumError, codes
from rostrum_core.merge import check_output

from .builder import Song
from .doc import KIND

SAFE_BUILTINS = {f.__name__: f for f in (range, len, min, max, abs, round, enumerate, zip, list, dict, tuple,
                                          float, int, str, sorted, sum, reversed)}
API = ["tempo(bpm)", "length(time)", "beats_per_bar(n)", "sample_rate(hz)", "track(id, **fields)",
       "marker(name, at)", "master(**fields)", "beat(n)", "beats(n)", "bar(n)"]


def scope(song: Song) -> dict:
    def bar(n):
        """The start of bar n (bar(1) is the start of the song)."""
        if n < 1:
            raise ValueError("bars count from 1")
        return {"beat": (n - 1) * song.root.get("beatsPerBar", 4)}
    return {
        "tempo": lambda bpm: song.set(tempo=bpm),
        "length": lambda t: song.set(length=t),
        "beats_per_bar": lambda n: song.set(beatsPerBar=n),
        "sample_rate": lambda hz: song.set(sampleRate=hz),
        "track": song.track, "marker": song.marker, "master": song.master,
        "beat": lambda n: {"beat": n}, "beats": lambda n: {"beats": n}, "bar": bar,
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
