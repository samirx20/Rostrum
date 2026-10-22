"""RostrumSound's screen states for the layout check (rostrum_gui/layout_run.py): each page, the open menus and
dialogs, and the long-text cases (a long song name, a long track name, many changes, a long status message).
A state is (name, start args, steps). Add one whenever a screen or panel is added."""
from __future__ import annotations

import tempfile
from pathlib import Path

from .sample import SOURCE

LONG_TRACK = "lead_guitar_line_for_the_second_verse_and_bridge"
LONG_AGENT = "Claude: moved the title card, softened the door knock, and rebalanced the whole second verse against the drums"
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
        ("instruments", ["--sample"], ["page instruments"]),
        ("timeline", ["--sample"], ["page timeline"]),
        ("mix", ["--sample"], ["page mix", "select melody"]),
        ("long-instruments", long_project(), [*busy, "page instruments"]),
        ("long-timeline", long_project(), [*busy, "page timeline"]),
        ("long-mix", long_project(), [*busy, "page mix"]),
        ("file-menu", long_project(), [*busy, "file-menu"]),
        ("song", ["--sample"], ["page timeline", "song-open"]),
        ("history-agent-run", ["--sample"], ["page timeline", "agent-run 6", "history open"]),
        ("agent-chip-long", long_project(), [*busy, "agent-run 3", f"agent-say {LONG_AGENT}"]),
        ("settings", ["--sample"], ["settings"]),
        ("commands", ["--sample"], ["commands"]),
        ("help-menu", ["--sample"], ["help"]),
        ("about", ["--sample"], ["about"]),
        ("connect-agent", ["--sample"], ["agents"]),
        ("guide", ["--sample"], ["guide first-song.md"]),
    ]
