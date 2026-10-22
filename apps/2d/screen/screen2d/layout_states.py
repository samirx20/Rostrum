"""Rostrum2D's screen states for the layout check (rostrum_gui/layout_run.py): the one workspace with each tool and
timeline height, one and several selected, the open panels and menus,
and the long-text cases (a long project name, a long layer name, many changes, a long status message).
A state is (name, start args, steps). Add one whenever a screen or panel is added."""
from __future__ import annotations

import tempfile
from pathlib import Path

from .sample import SOURCE

LONG_LAYER = "Title card for the summer launch film, second take"
LONG_ERROR = ("The drawing engine stopped and could not be restarted: the engine program was ended from outside twice "
              "within a minute (exit code 1), so drawing stopped. Save, then reopen Rostrum2D.")
LONG_AGENT = "Claude: moved the title card, changed its colour, and re-timed the whole opening against the music"
LONG_STATUS = "No graphics driver, so drawing is slower"
LONG_PROJECT = "Summer_launch_film_for_the_new_headphones_-_final_cut_v3"   # a step's words: _ for spaces
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
    """Start args for a project with sound (sound_sample.sound_project), made fresh in the temp folder."""
    from .sound_sample import sound_project
    return sound_project(Path(tempfile.mkdtemp(dir=SCRATCH.name)) / "With sound")


def with_video_sound() -> list[str]:
    """The sound project plus a video with its own sound (sound_sample.video_sound_project): the Video sound row."""
    from .sound_sample import video_sound_project
    return video_sound_project(Path(tempfile.mkdtemp(dir=SCRATCH.name)) / "Video sound")


def with_character() -> list[str]:
    """Start args for the small character project (rig_sample.py), made fresh in the temp folder."""
    from .rig_sample import character_project
    return character_project(Path(tempfile.mkdtemp(dir=SCRATCH.name)) / "Character")


RIGGED = ["select max", "run layer:rig", "run layer:guess_bones", "bones"]     # H32: a rig with bones from part names
MOUTHS = ["selectmany mouth_rest mouth_M_B_P mouth_E mouth_O mouth_A mouth_F_V", "run layer:swap"]


LONG_FOLDER = r"C:\Users\Sam\Documents\Rostrum_projects\Summer_launch_film_for_the_new_headphones\deliveries\final_round_three_for_the_client"


def states() -> list[tuple[str, list[str], list[str]]]:
    long = long_project            # a fresh folder per state: each state's steps start from the same document
    busy = [*TWELVE, f"rename card {LONG_LAYER}", f"say {LONG_STATUS}"]
    return [
        ("workspace", ["--sample"], ["select title"]),
        ("rig-make-first", with_character(), ["select max"]),                # H32: parts named like a body: Make rig first
        ("rig-bones", with_character(), RIGGED),                             # H32: the bone overlay, a rig in hand
        ("rig-attach", with_character(), [*RIGGED, "selectmany hand_R bone_5"]),   # a part + a bone: Attach to bone
        ("rig-poses", with_character(), [*RIGGED, "posesave", "posesave", "inspectorscroll 900"]),   # the Poses list
        ("lipsync-sheet", with_character(), [*RIGGED, *MOUTHS, "run layer:lipsync"]),             # Lip sync…
        ("blinks-sheet", with_character(), [*RIGGED, "selectmany eyes_open eyes_closed", "run layer:swap", "run layer:blinks"]),
        ("sound-row", with_sound(), ["sound wait", "select logo"]),          # the Sound row, its waveform, 🔊
        ("sound-beats", with_sound(), ["sound beats on", "rulermenu"]),       # Show beats, the ruler's ▾ menu
        ("sound-compact", with_sound(), ["sound wait", "select logo", "timeline compact"]),
        ("sound-menu", with_sound(), ["sound wait", "sound menu"]),           # Open in RostrumSound
        ("sound-cue-picker", with_sound(), ["sound wait", "select logo", "sound cue whoosh"]),   # H32: Add a sound here…
        ("export-sheet-sound", with_sound(), ["sound wait", "exportsheet open mp4"]),          # H32: Include the project's sound
        ("video-sound-row", with_video_sound(), ["sound wait", "select talk", "sound video"]),  # H33: a video's own sound
        ("video-sound-muted", with_video_sound(), ["sound wait", "sound video talk on", "timeline compact"]),
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
        ("file-menu-sample", ["--sample"], ["filemenu open"]),                 # File > Open sample
        ("long-status-line", ["--sample"], [f"say {LONG_ERROR}"]),               # elided with the whole text on hover
        ("expression-typed", ["--sample"], ["select title", "set x =sin(time * 2) * 40 + 640", "open title"]),   # `=…` typed
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
        # H32: a named frame size on Scene settings; the Camera tool (only with a camera) over the canvas; the Effects menu
        ("scene-size", ["--sample"], ["select screen_sample", "set size vertical"]),
        ("camera-tool", ["--sample"], ["add camera", "tool camera"]),
        ("effects-menu", ["--sample"], ["select card", "clickbtn Effects", "wait 300"]),
        ("rename-name", long(), ["name edit"]),                               # S35: the name clicked, the kit's rename field
        ("show-only-kinds", ["--sample"], ["selectmany title card dot"]),     # S35: mixed kinds, the panel's Show only lines
        # H33: Set depth ▾ › Other depth… open (a typed number); picked strokes turned by their knob (handles on the box)
        ("depth-typed", ["--sample"], ["tool draw", "draw 300 300 500 320 700 300", "tool move", "add camera",
                                       "select drawing_1", "depthtyped 2.5 open"]),
        ("paint-strokes-turned", ["--sample"], [*PAINTED, "lasso 500,200 1300,200 1300,400 500,400",
                                                "strokeshandle turn 1100 120"]),
        # H33 r2: strokes at the top of the canvas: their turn knob sits below the box, clear of the context bar
        ("paint-knob-below", ["--sample"], ["tool draw", "draw 760 30 960 70 1160 30",
                                            "lasso 700,0 1220,0 1220,140 700,140"]),
        # H33 (rig): the Bone tool mid-chain; Mirror pose ▾ open; faint copies of Repeat; a key's beat words on the bar
        ("bone-tool", with_character(), ["select max", "run layer:rig", "bonedrag 640 420 640 240", "boneclick 640 130",
                                         "bonehover 600 150"]),
        ("mirror-pose-menu", with_character(), [*RIGGED, "clickbtn Mirror pose", "wait 300"]),
        ("key-faint-copies", ["--sample"], ["select dot", "keypick dot.x.k2200", "keyafter repeat"]),
        ("key-beat-words", with_sound(), ["sound wait", "select logo", "time 1.0", "keyhere", "showanim",
                                          "keypick logo.x.k1000"]),
        # H33 (rig, round 2): Styles ▾ on a text with a saved style; the Library drawer without a project and with a
        # brand kit of long names
        ("styles-menu", ["--sample"], ["select title", "do layer:style_save", "add text", "clickbtn Styles", "wait 300"]),
        ("library-no-project", ["--sample"], ["library open", "select title"]),
        ("library-brand", long_project(), ["select title_card_for_the_summer_launch_film", "do layer:style_save",
                                           "brand colors Summer_launch_coral_for_the_headphones_campaign #ff7a59",
                                           "brand colors Night #101820",
                                           f"brand textStyles {LONG_LAYER.replace(' ', '_')} textstyle_1", "library open"]),
    ]
