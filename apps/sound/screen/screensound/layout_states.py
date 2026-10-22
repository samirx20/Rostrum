"""RostrumSound's screen states for the layout check (rostrum_gui/layout_run.py): the empty song, the workspace with
the Editor, the Mixer or the Library open, the Export sheet, the open menus and dialogs, and the long-text
cases (a long song name, a long track name, many changes, a long status message).
A state is (name, start args, steps). Add one whenever a screen or panel is added."""
from __future__ import annotations

import tempfile
from pathlib import Path

from .sample import SOURCE

LONG_TRACK = "lead_guitar_line_for_the_second_verse_and_bridge"
LONG_STATUS = "No graphics driver, so drawing is slower"
TWELVE = [f"select {LONG_TRACK}"] + [f"set volume {0.5 + n / 100}" if n % 2 else f"set pan {n / 100}" for n in range(12)]
IGNORE = ()
SCRATCH = tempfile.TemporaryDirectory(prefix="rostrum-layout-")      # removed when the check run ends


def long_project() -> list[str]:
    """Start args for a saved song in a folder with a long name (a fresh folder each time)."""
    folder = Path(tempfile.mkdtemp(dir=SCRATCH.name)) / "Summer launch film for the new headphones - final score v3"
    script = folder.parent / "long_names.py"
    script.write_text(SOURCE.replace('track("melody"', f'track("{LONG_TRACK}"'), encoding="utf-8")
    return ["--doc", str(folder), "song", "--script", str(script)]


def states() -> list[tuple[str, list[str], list[str]]]:
    busy = [*TWELVE, f"say {LONG_STATUS}"]
    return [
        ("empty-song", ["--new"], []),
        ("editor", ["--sample"], ["dock editor", "select melody"]),
        ("mixer", ["--sample"], ["dock mixer", "select drums"]),
        ("library", ["--sample"], ["library"]),
        ("draw", ["--sample"], ["select melody", "dock editor", "tool draw"]),
        ("voice-lines", ["--sample"], ["add-track voice:ryan", "dock editor"]),
        ("grid-menu", ["--sample"], ["grid-open"]),
        ("export", ["--sample"], ["deliver streaming", "export-open"]),
        ("long-export", long_project(), [*busy, "deliver streaming", "export-open"]),
        ("long-editor", long_project(), [*busy, "dock editor"]),
        ("long-mixer", long_project(), [*busy, "dock mixer"]),
        ("long-library", long_project(), [*busy, "library"]),
        ("file-menu", long_project(), [*busy, "file-menu"]),
        ("song", ["--sample"], ["song-open"]),
        ("settings", ["--sample"], ["settings"]),
        ("commands", ["--sample"], ["commands"]),
        ("help-menu", ["--sample"], ["help"]),
        ("about", ["--sample"], ["about"]),
        ("connect-agent", ["--sample"], ["agents"]),
        ("guide", ["--sample"], ["guide first-song.md"]),
    ]
