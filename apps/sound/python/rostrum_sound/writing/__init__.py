"""Writing helpers for Sound scripts: harmony, bass, arpeggios, drums and development, as plain notes.

Every helper returns a *line* (a list of {"pitch"|"drum", "at", "dur", "vel"} in beats from its own start, line.py);
`write(track, line, at)` puts it on a track through the track's own note / hit, so the document holds ordinary notes
a person can edit, and a re-run keeps their edits. The key and bar length default to the song's (the last `key(...)`
set and the starting beats per bar); a 16th-step pattern counts four steps per beat.

    roman("V7/V", key="C major") -> "D7"                       voice(["Am", "F", "C", "G"], voicing="led") -> notes
    comp(["i", "VI", "III", "VII"], rhythm="x..x..x.", push=0.5)  bass_line(prog, style="walking", approach=True)
    arp(prog, mode="upDown", rate=0.25, octaves=2)               drum_grid({"kick": "x...", "hat": "x.x."}, bars=4, fill="toms")
    vary(motif, "steps:1+displace:0.5")                         develop(motif, repeat=4, vary=["same", "steps:1", "same", "end:-1"])
    line([("D4", 0, 1), ("F4", 1, 0.5, 0.8)]) ; shift(line, 8) ; write(track, line, at=bar(5))

The craft guide is apps/sound/guides/writing-music.md (inspect_guide 'writing-music').
"""
from __future__ import annotations

from ..script_time import Beats
from .bass import STYLES as BASS_STYLES
from .bass import bass_line
from .comp import arp, comp
from .drums import drum_grid
from .line import line, shift, write
from .ops import develop, vary
from .pitch import roman, tones
from .voicing import voice

API = ['roman(numeral, key)', 'chord_tones(chord, key)', 'voice(chords, voicing="led", range=("G3", "D5"), ...)',
       'comp(chords, rhythm="hold", per=bar, push=0, ...)', 'bass_line(chords, style="root" | pattern=..., approach=False, ...)',
       'arp(chords_or_notes, mode="up", rate=0.5, pattern=None, octaves=1, ...)', 'drum_grid({drum: steps}, bars=1, fill=None, ...)',
       'vary(line, "ops")', 'develop(line, repeat, vary=[ops, ...])', 'line([(pitch, at, dur, vel), ...])', 'shift(line, beats)',
       'write(track, line, at)']


def scope(song) -> dict:
    """The helpers for one script run, with the song's key and bar length as defaults (read when each is called)."""
    def song_key(given):
        if given is not None:
            return given
        keys = song.root.get("keys") or []
        return keys[-1]["key"] if keys else None

    def bpb(given):
        return given if given is not None else song.root.get("beatsPerBar", 4)

    def with_song(fn, name, per=False):
        def call(*args, key=None, beats_per_bar=None, **kw):
            kw = {k: v["beats"] if isinstance(v, Beats) else v for k, v in kw.items()}     # per=beats(8) reads as 8
            b = bpb(beats_per_bar)
            if per and "per" not in kw:
                kw["per"] = b
            return fn(*args, key=song_key(key), beats_per_bar=b, where=name, **kw)
        call.__name__, call.__doc__ = name, fn.__doc__
        return call
    return {
        "roman": lambda numeral, key=None: roman(numeral, song_key(key), "roman"),
        "chord_tones": lambda chord, key=None: _names(tones(chord, "chord_tones", song_key(key)), song_key(key)),
        "voice": lambda chords, key=None, **kw: voice(chords, song_key(key), where="voice", **kw),
        "comp": with_song(comp, "comp", per=True),
        "bass_line": with_song(bass_line, "bass_line", per=True),
        "arp": with_song(arp, "arp", per=True),
        "drum_grid": lambda patterns, beats_per_bar=None, **kw: drum_grid(patterns, beats_per_bar=bpb(beats_per_bar), **kw),
        "vary": with_song(vary, "vary"),
        "develop": with_song(develop, "develop"),
        "line": line, "shift": shift, "write": write,
    }


def _names(t: dict, key) -> list[str]:
    """A chord's tones as pitch-class names, root first: chord_tones("Am7") -> ["A", "C", "E", "G"]."""
    from ..doc.keys import pc_name
    return [pc_name(p, key) for p in t["pcs"]]


__all__ = ["scope", "API", "BASS_STYLES", "roman", "tones", "voice", "comp", "bass_line", "arp", "drum_grid", "vary",
           "develop", "line", "shift", "write"]
