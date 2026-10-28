"""The script call `beats()`: every beat time (comp seconds) of the music that plays with the current scene, read from
RostrumSound's tempo grid (project_sound.beats: the same beats as the Sound row's lines and an expression's pulse()).
The music itself is made in RostrumSound (AGENTS.md rule 9: its run_script, a song with `marker()`s); a 2D script
only times its layers to it: a song's marker by name (`.key("x", {"#drop": 0})`, `start="#drop"`), or its beats here.

    b = beats()                                   # [0.0, 0.5, 1.0, …] up to the scene's length
    for i, t in enumerate(b[8:16]):               # one bar of cuts on beats 8 … 15
        layer(f"shot{i}").set(start=t)

Fails loudly when the project has no song yet (make it in RostrumSound first) or the script runs outside a project."""
from __future__ import annotations


def for_script(build) -> dict:
    def beats(start=0.0, end=None):
        """The beats from `start` to `end` seconds (default: the scene's length), in comp seconds."""
        from . import project_sound
        from .lipsync.script import _folder
        if not build.holders:
            raise ValueError("beats(): make the scene first (comp(...)): its soundtrack and length say which beats")
        comp = build.holders[0]
        last = float(comp.get("duration", 10.0) if end is None else end)
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
