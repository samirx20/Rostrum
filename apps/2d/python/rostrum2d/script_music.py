"""The script call `beats()`: every beat time (comp seconds) of the music that plays with the current scene, read from
RostrumSound's tempo grid (project_sound.beats: the same beats as the Sound row's lines and an expression's pulse()).
The music itself is made in RostrumSound (AGENTS.md rule 9: its run_script, a song with `marker()`s); a 2D script
only times its layers to it: a song's marker by name (`.key("x", {"#drop": 0})`, `start="#drop"`), or its beats here.

    b = beats()                                   # [0.0, 0.5, 1.0, …] up to the scene's length
    for i, t in enumerate(b[8:16]):               # one bar of cuts on beats 8 … 15
        layer(f"shot{i}").set(start=t)
    beats(bpm=120, start="#in", count=8)          # no song: a grid of 8 beats from the marker "in" ("#in", "#in+0.5", …)

beats() fails loudly when the project has no song yet (make it in RostrumSound first) or the script runs outside a
project; beats(bpm=) needs neither. start / end may be a marker time ("#drop"); the song's beats come back in seconds,
a bpm grid from a marker start as marker times (they move with the marker)."""
from __future__ import annotations


def for_script(build) -> dict:
    def beats(start=0.0, end=None, bpm=None, count=None):
        """The beats from `start` to `end` (default: the scene's length): the song's, or every 60/bpm s with `bpm`."""
        from . import project_sound
        from .lipsync.script import _folder
        from .script_time import Time, seconds
        if not build.holders:
            raise ValueError("beats(): make the scene first (comp(...)): its soundtrack and length say which beats")
        comp = build.holders[0]
        first = seconds(build, start, "beats(start=…)")
        last = float(comp.get("duration", 10.0)) if end is None else seconds(build, end, "beats(end=…)")
        if bpm is not None:
            if isinstance(bpm, bool) or not isinstance(bpm, (int, float)) or not 0 < bpm <= 1000:
                raise ValueError(f"beats(bpm={bpm!r}): beats a minute, a number above 0 (120 is two a second)")
            if count is not None and (not isinstance(count, int) or count < 1):
                raise ValueError(f"beats(count={count!r}): how many beats, a whole number 1 or more")
            step, base = 60.0 / bpm, Time(start) if isinstance(start, str) else first
            n = count if count is not None else int((last - first) / step + 1e-6) + 1
            return [base + round(i * step, 6) if isinstance(base, Time) else round(base + i * step, 6) for i in range(max(0, n))]
        if count is not None:
            raise ValueError("beats(count=…) goes with bpm= (a grid without a song); the song's beats stop at end=")
        start = first
        folder = _folder()
        if folder is None:
            raise ValueError("beats(): this script runs outside a project, so there is no music to read; run it with "
                             "run_script in the project that has the song")
        found = project_sound.beats(folder, comp.get("soundtrack", ""), last)
        if found is None:
            raise ValueError("beats(): the project has no song yet. Make the music in RostrumSound first (its run_script; "
                             "guide timing-to-music), then re-run this script: beats() reads the song's tempo")
        return [round(t, 6) for t in found if start - 1e-6 <= t <= last + 1e-6]

    return {"beats": beats}
