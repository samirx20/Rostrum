"""Rostrum2D's screen states for the layout check (rostrum_gui/layout_run.py): the one workspace with each tool and
timeline height, one and several selected, the open panels and menus,
and the long-text cases (a long project name, a long layer name, many changes, a long status message).
A state is (name, start args, steps). Add one whenever a screen or panel is added."""
from __future__ import annotations

import tempfile
from pathlib import Path

from .sample import SOURCE

LONG_LAYER = "Title card for the summer launch film, second take"
LONG_AGENT = "Claude: moved the title card, changed its colour, and re-timed the whole opening against the music"
LONG_STATUS = "No graphics driver, so drawing is slower"
LONG_PROJECT = "Summer_launch_film_for_the_new_headphones_-_final_cut_v3"   # a step's words: _ for spaces
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


LONG_FOLDER = r"C:\Users\Sam\Documents\Rostrum_projects\Summer_launch_film_for_the_new_headphones\deliveries\final_round_three_for_the_client"


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
        ("start-screen", long(), [f"duplicateproject {LONG_PROJECT}_{n}" for n in (2, 3)] + ["startscreen open"]),   # long recent names
        ("history-agent-run", ["--sample"], ["select title", "agent-run 6", "history open"]),
        ("agent-chip-long", long(), [*busy, "agent-run 3", f"agent-say {LONG_AGENT}"]),
        ("add-menu", ["--sample"], ["addmenu open"]),
        ("export-sheet", long(), [*busy, "exportsheet open png", f"exportwhere {LONG_FOLDER}"]),     # S34: the kit sheet
        ("job-chip", long(), [*busy, "job-show 42"]),
        ("job-failed", long(), [*busy, "job-failed The engine stopped while drawing frame 112: the GPU ran out of memory. Try a smaller size."]),
        ("import-panel", ["--sample"], ["importpanel open"]),
        ("problems-chip", long(), [*busy, "problems-demo", "problems open"]),
        ("commands", ["--sample"], ["commands"]),
        ("help-menu", ["--sample"], ["help"]),
        ("about", ["--sample"], ["about"]),
        ("connect-agent", ["--sample"], ["agents"]),
        ("guide", ["--sample"], ["guide the-screen.md"]),
        ("guides-list", ["--sample"], ["guides open"]),                       # the kit's guides drawer (F1)
        ("guides-find", ["--sample"], ["guides find a_word_no_guide_has_anywhere_in_its_text_at_all"]),
        ("key-list", ["--sample"], ["keylist open"]),                          # Ctrl+/
        ("panels-folded", ["--sample"], ["panels fold"]),                      # Ctrl+\
        ("view-menu", ["--sample"], ["select title", "zoom 400", "viewmenu"]),     # zoomed in, the view's % menu open
        # H29: the creation tools, the context bar's tool options, keys picked in the timeline
        ("rect-drawing", ["--sample"], ["shapedrag rect 300 200 900 600"]),
        ("typing", ["--sample"], ["typetext 300 300 Spring_launch"]),
        ("long-typing", long(), [*busy, "typetext 300 300 Spring_launch_for_the_new_headphones"]),
        ("pen-tool", ["--sample"], ["tool pen", "pen 300,300 600,320"]),
        ("paint-on-shape", ["--sample"], ["select card", "tool draw", "draw 600 300 900 330 1200 300"]),
        ("keys-picked", ["--sample"], ["select title", "showanim", "keypick title.opacity.k900", "keypick title.y.k1000 ctrl"]),
    ]
