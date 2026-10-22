"""Rostrum2D's screen states for the layout check (rostrum_gui/layout_run.py): the one workspace with each tool and
timeline height, one and several selected, the open panels and menus,
and the long-text cases (a long project name, a long layer name, many changes, a long status message).
A state is (name, start args, steps). Add one whenever a screen or panel is added."""
from __future__ import annotations

import tempfile
from pathlib import Path

from .sample import SOURCE

LONG_LAYER = "Title card for the summer launch film, second take"
LONG_STATUS = "No graphics driver, so drawing is slower"
TWELVE = ["select card"] + [f"set {'xy'[n % 2]} {500 + n}" for n in range(12)]   # 12 changes (x, y in turn: no merging)
# What the check leaves out on purpose: the canvas' own handles are small drag targets on the picture by design.
IGNORE = ()
SCRATCH = tempfile.TemporaryDirectory(prefix="rostrum-layout-")      # removed when the check run ends


def long_project() -> list[str]:
    """Start args for a saved project in a folder with a long name (made fresh in the temp folder)."""
    folder = Path(tempfile.mkdtemp(dir=SCRATCH.name)) / "Summer launch film for the new headphones - final cut v3"
    script = folder.parent / "long_names.py"
    script.write_text(SOURCE.replace('"title"', '"title_card_for_the_summer_launch_film"'), encoding="utf-8")
    return ["--doc", str(folder), "main", "--script", str(script)]


def states() -> list[tuple[str, list[str], list[str]]]:
    long = long_project            # a fresh folder per state: each state's steps start from the same document
    busy = [*TWELVE, f"rename card {LONG_LAYER}", f"say {LONG_STATUS}"]
    return [
        ("workspace", ["--sample"], ["select title"]),
        ("rows-open", ["--sample"], ["select title", "open title"]),
        ("two-selected", ["--sample"], ["selectmany title card"]),
        ("action-menu", ["--sample"], ["selectmany dot rule", "actionmenu"]),
        ("context-bar-one", ["--sample"], ["select title"]),
        ("context-bar-two", ["--sample"], ["selectmany title card"]),
        ("right-click", ["--sample"], ["selectmany title card", "canvasmenu"]),
        ("ctrl-k", ["--sample"], ["selectmany title card", "commands"]),
        ("find-setting", ["--sample"], ["select title", "find marker"]),
        ("draw-tool", ["--sample"], ["select title", "tool draw"]),
        ("timeline-full-draw", ["--sample"], ["tool draw", "timeline full"]),
        ("curves", ["--sample"], ["select title", "curves on"]),
        ("long-workspace", long(), busy),
        ("long-rows-open", long(), [*busy, "open card"]),
        ("long-draw", long(), [*busy, "tool draw"]),
        ("file-menu", long(), [*busy, "filemenu open"]),
        ("add-menu", ["--sample"], ["addmenu open"]),
        ("export-panel", long(), [*busy, "exportpanel open"]),
        ("import-panel", ["--sample"], ["importpanel open"]),
        ("problems", ["--sample"], ["problems open"]),
        ("commands", ["--sample"], ["commands"]),
        ("help-menu", ["--sample"], ["help"]),
        ("about", ["--sample"], ["about"]),
        ("connect-agent", ["--sample"], ["agents"]),
        ("guide", ["--sample"], ["guide the-screen.md"]),
    ]
