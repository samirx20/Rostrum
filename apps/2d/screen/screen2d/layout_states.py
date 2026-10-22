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
PAINTED = ["select card", "tool draw", "draw 600 300 900 330 1200 300"]
LONG_PAINT = 'paint_3 name "Line art for the summer launch film, cleaned up"'     # the third paint layer, renamed
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


def with_sound() -> list[str]:
    """Start args for a project with sound (soundtrack_steps.sound_project), made fresh in the temp folder."""
    from .soundtrack_steps import sound_project
    return sound_project(Path(tempfile.mkdtemp(dir=SCRATCH.name)) / "With sound")


def states() -> list[tuple[str, list[str], list[str]]]:
    long = long_project            # a fresh folder per state: each state's steps start from the same document
    busy = [*TWELVE, f"rename card {LONG_LAYER}", f"say {LONG_STATUS}"]
    return [
        ("workspace", ["--sample"], ["select title"]),
        ("sound-row", with_sound(), ["sound wait", "select logo"]),          # the Sound row, its waveform, 🔊
        ("sound-beats", with_sound(), ["sound beats on", "rulermenu"]),       # Show beats, the ruler's ▾ menu
        ("sound-compact", with_sound(), ["sound wait", "select logo", "timeline compact"]),
        ("sound-menu", with_sound(), ["sound wait", "sound menu"]),           # Open in RostrumSound
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
        ("history-agent-run", ["--sample"], ["select title", "agent-run 6", "history open"]),
        ("agent-chip-long", long(), [*busy, "agent-run 3", f"agent-say {LONG_AGENT}"]),
        ("add-menu", ["--sample"], ["addmenu open"]),
        ("export-panel", long(), [*busy, "exportpanel open"]),
        ("import-panel", ["--sample"], ["importpanel open"]),
        ("problems", ["--sample"], ["problems open"]),
        ("commands", ["--sample"], ["commands"]),
        ("help-menu", ["--sample"], ["help"]),
        ("about", ["--sample"], ["about"]),
        ("connect-agent", ["--sample"], ["agents"]),
        ("guide", ["--sample"], ["guide the-screen.md"]),
        ("view-menu", ["--sample"], ["select title", "zoom 400", "viewmenu"]),     # zoomed in, the view's % menu open
        # H29: the creation tools, the context bar's tool options, keys picked in the timeline
        ("rect-drawing", ["--sample"], ["shapedrag rect 300 200 900 600"]),
        ("typing", ["--sample"], ["typetext 300 300 Spring_launch"]),
        ("long-typing", long(), [*busy, "typetext 300 300 Spring_launch_for_the_new_headphones"]),
        ("pen-tool", ["--sample"], ["tool pen", "pen 300,300 600,320"]),
        ("paint-on-shape", ["--sample"], ["select card", "tool draw", "draw 600 300 900 330 1200 300"]),
        ("keys-picked", ["--sample"], ["select title", "showanim", "keypick title.opacity.k900", "keypick title.y.k1000 ctrl"]),
        # H30: the key bar (one key; a spring), a key's Ease list, Stagger's popover
        ("key-bar-one", ["--sample"], ["select title", "showanim", "keypick title.opacity.k900"]),
        ("key-bar-spring", ["--sample"], ["select title", "showanim", "keypick title.y.k200", "easeplay off", "ease spring"]),
        ("key-ease-menu", ["--sample"], ["select title", "showanim", "keypick title.y.k200", "easemenu"]),
        ("stagger-popover", ["--sample"], ["selectmany title card", "stagger 3 open"]),
        # H31: the key bar's ⋯ (After the last key, Play the ease), the "+6 f · key" label mid-drag, Stagger on keys
        ("key-more-menu", ["--sample"], ["select dot", "keypick dot.x.k2200", "keyafter pingpong", "keymore"]),
        ("key-drag-label", ["--sample"], ["select dot", "time 3", "keypick dot.x.k1000", "keypick dot.x.k2200 ctrl",
                                          "keystretch dot.x.k2200 2.2 2.03 snap hold"]),
        ("stagger-keys", ["--sample"], ["keypick card.scale.k0,card.scale.k800", "keypick title.y.k200 ctrl",
                                        "keypick dot.x.k1000 ctrl", "stagger 9 picked open"]),
        # H30: painting's bar (Fill on, Close gaps), the "Paint on …" group with 3 paint layers, one with a long name
        ("paint-fill", ["--sample"], [*PAINTED, "fillmode on"]),
        ("paint-layers", ["--sample"], [*PAINTED, "paintlayer", "draw 600 400 1200 420", "paintlayer",
                                        "draw 600 500 1200 520", f"paintset {LONG_PAINT}"]),
        # H31: Select strokes armed; strokes picked (their bar); Alt held over a colour; Set depth on a drawing with a camera
        ("paint-select-strokes", ["--sample"], [*PAINTED, "selectstrokes on"]),
        ("paint-strokes-picked", ["--sample"], [*PAINTED, "lasso 500,200 1000,200 1000,400 500,400"]),
        ("paint-alt-pick", ["--sample"], [*PAINTED, "altpick 750 310"]),
        ("set-depth", ["--sample"], ["tool draw", "draw 300 300 500 320 700 300", "tool move", "add camera", "select drawing_1"]),
    ]
