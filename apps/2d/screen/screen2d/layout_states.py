"""Rostrum2D's screen states for the layout check (rostrum_gui/layout_run.py): the one workspace with each tool and
timeline height, one and several selected, the open panels and menus,
and the long-text cases (a long project name, a long layer name, many changes, a long status message).
A state is (name, start args, steps). Add one whenever a screen or panel is added; name it in QUICK when it is one of
the most important (the quick check runs those)."""
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
PICTURE = (Path(__file__).resolve().parents[4] / "proofs" / "3d-painterly" / "paint" / "textures" / "cloth.png").as_posix()  # a real
# picture for a fill (a screenshot of the app, dark, reads as a broken fill)
PAINTED = ["select card", "tool draw", "draw 600 300 900 330 1200 300"]
FRAMES = ["tool draw", "draw 300 300 500 320 700 300", "newframe", "draw 320 320 520 340 720 320", "newframe copy",
          "draw 340 340 540 360 740 340"]
LONG_PAINT = 'paint_3 name "Line art for the summer launch film, cleaned up"'     # the third paint layer, renamed
TWELVE = ["select card"] + [f"set {'xy'[n % 2]} {500 + n}" for n in range(12)]   # 12 changes (x, y in turn: no merging)
# What the check leaves out on purpose: the canvas' own handles are small drag targets on the picture by design.
IGNORE = ()
# The most important states: `main.py --check-layout <folder> --quick` runs just these, at 1646x900 (Sam's screen), in
# about 2 minutes. Every brief runs it before reporting; the full run (every state, four sizes) stays for merges and audits.
QUICK = ("workspace", "long-workspace", "rows-open", "two-selected", "draw-tool", "right-click", "action-menu", "ctrl-k",
         "file-menu", "start-screen", "export-sheet", "guides-list", "guide", "help-menu", "about", "key-list", "view-menu",
         "panels-folded", "animation-picked", "key-bar-spring", "brush-panel", "paint-layers", "fill-gradient-handles",
         "sound-row", "rig-bones", "camera-ride", "scene-1080x1920", "long-status-line")
SCRATCH = tempfile.TemporaryDirectory(prefix="rostrum-layout-")      # removed when the check run ends


def long_project() -> list[str]:
    """Start args for a saved project in a folder with a long name (made fresh in the temp folder)."""
    folder = Path(tempfile.mkdtemp(dir=SCRATCH.name)) / "Summer launch film for the new headphones - final cut v3"
    script = folder.parent / "long_names.py"
    script.write_text(SOURCE.replace('"title"', '"title_card_for_the_summer_launch_film"'), encoding="utf-8")
    return ["--doc", str(folder), "main", "--script", str(script)]


CLOSE_KEYS = SOURCE.replace("duration=4", "duration=12").replace("{0.2: 0, 0.9: 1}", "{1.0: 0, 1.0333: 0.3, 1.0667: 0.6, 4.0: 1}")


def close_keys() -> list[str]:
    """Start args for a 12 s scene whose title has keys one frame apart (zoomed out they would sit on each other)."""
    script = Path(tempfile.mkdtemp(dir=SCRATCH.name)) / "close_keys.py"
    script.write_text(CLOSE_KEYS, encoding="utf-8")
    return ["--script", str(script)]


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


def picture() -> str:
    """A plain picture file in the temp folder (Mask's state: a picture and a shape)."""
    from PySide6.QtGui import QColor, QImage
    path = Path(tempfile.mkdtemp(dir=SCRATCH.name)) / "sunset.png"
    img = QImage(400, 300, QImage.Format_RGB32)
    img.fill(QColor("#d08040"))
    img.save(str(path))
    return path.as_posix()


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
        ("sound-beats", with_sound(), ["sound beats on", "sound menu"]),     # Show beats, the Sound row's menu
        ("sound-compact", with_sound(), ["sound wait", "select logo", "timeline compact"]),
        ("sound-menu", with_sound(), ["sound wait", "sound menu"]),           # Open in RostrumSound
        ("sound-cue-picker", with_sound(), ["sound wait", "select logo", "sound cue"]),   # H32: Add a sound here…
        ("export-sheet-sound", with_sound(), ["sound wait", "exportsheet open mp4"]),          # H32: Project sound
        ("video-sound-row", with_video_sound(), ["sound wait", "select talk", "sound video"]),  # H33: a video's own sound
        ("video-sound-muted", with_video_sound(), ["sound wait", "sound video talk on", "timeline compact"]),
        ("rows-open", ["--sample"], ["select title", "open title"]),
        ("rows-folded", ["--sample"], ["select title", "open title", "fold title"]),   # a folded layer: its one row, no lines under it
        ("playhead-on-key", ["--sample"], ["select title", "time 1.0"]),     # the playhead exactly on a key
        ("two-selected", ["--sample"], ["selectmany title card"]),
        ("action-menu", ["--sample"], ["selectmany dot rule", "actionmenu"]),
        # H60: keys a frame apart on a zoomed-out timeline: one dot standing for the run (a second diamond behind it)
        ("close-keys", close_keys(), ["select title", "showanim", "timeline full"]),
        ("two-shapes", ["--sample"], ["selectmany dot rule"]),               # H49: compact actions, slim key-span bars
        ("gradient-handles", ["--sample"], ["select card", "clickname swatch", "clickname fillType:linear"]),
        # H47: the frame drives the layout (SPEC 2d-design-v2 §1.2): tall and square scenes put the timeline beside it
        *[(f"scene-{w}x{h}", ["--sample"], ["select screen_sample", f"set width {w}", f"set height {h}", "select title"])
          for w, h in ((1080, 1920), (1080, 1080), (1080, 1350))],
        ("animation-picked", ["--sample"], ["select title", "clickname stretch:title.opacity.k200"]),   # §9.3: the animation view
        ("right-click", ["--sample"], ["selectmany title card", "canvasmenu"]),
        # H48: the selection's actions at the top of the settings panel; right-click is the one short menu
        ("picture-shape", ["--sample"], [f"drop {picture()} 900 500", "selectmany image_1 card"]),     # Mask first
        ("animation-spring", ["--sample"], ["select title", "clickname stretch:title.opacity.k200", "clickname preset:spring"]),
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
        ("flyout-shapes", ["--sample"], ["flyout shapes"]),
        ("flyout-media", ["--sample"], ["flyout media"]),
        ("flyout-view", ["--sample"], ["tool zoom", "flyout view"]),
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
        ("start-screen-guide", ["--sample"], ["startscreen open", "guide text-on-a-path.md"]),   # no timeline under it
        ("guides-list", ["--sample"], ["guides open"]),                       # the kit's guides drawer (F1)
        ("guides-find", ["--sample"], ["guides find a_word_no_guide_has_anywhere_in_its_text_at_all"]),
        ("key-list", ["--sample"], ["keylist open"]),                          # Ctrl+/
        ("panels-folded", ["--sample"], ["panels fold"]),                      # Ctrl+\
        ("view-menu", ["--sample"], ["select title", "zoom 400", "viewmenu"]),     # zoomed in, the view's % menu open
        ("view-menu-blur", ["--sample"], ["select screen_sample", "set shutter 180", "viewmenu"]),   # H61: a blurred scene adds "Motion blur while playing"
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
        # H55: Paint layers + : a locked layer with a long name and its blend note (Multiply · 70 %) beside it
        ("paint-layers-locked", ["--sample"], [*PAINTED, "paintlayer", "draw 600 400 1200 420", "paintlayer",
                                               f"paintset {LONG_PAINT}", 'paintset paint_3 mode "multiply"',
                                               "paintset paint_3 opacity 0.7", "paintset paint_3 locked true"]),
        # H31: Select strokes armed; strokes picked (their bar); Alt held over a colour; Set depth on a drawing with a camera
        ("paint-select-strokes", ["--sample"], [*PAINTED, "selectstrokes on"]),
        ("paint-strokes-picked", ["--sample"], [*PAINTED, "lasso 500,200 1000,200 1000,400 500,400"]),
        ("paint-alt-pick", ["--sample"], [*PAINTED, "altpick 750 310"]),
        ("set-depth", ["--sample"], ["tool draw", "draw 300 300 500 320 700 300", "tool move", "add camera", "select drawing_1"]),
        # H32: a named frame size on Scene settings; the Camera tool (only with a camera) over the canvas; the Effects menu
        ("scene-size", ["--sample"], ["select screen_sample", "set size vertical"]),
        ("camera-tool", ["--sample"], ["add camera", "tool camera"]),
        ("effects-menu", with_character(), [*RIGGED, "inspectorscroll 900", "clickname addEffect", "wait 300"]),
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
        ("styles-menu", ["--sample"], ["select title", "do layer:style_save", "add text", "clickobj actionBar:Styles", "wait 300"]),   # Styles ▾ (ActionsSection)
        ("library-no-project", ["--sample"], ["library open", "select title"]),
        # S47: colour rows are a swatch square + hex box; a gradient fill shows its name in the box
        ("fill-solid-hex", ["--sample"], ["select card"]),
        ("fill-gradient-name", ["--sample"], ["select card", 'set paint {"type":"linear","angle":90,"stops":['
                                              '{"at":0,"color":"#ff7a45","opacity":1},{"at":1,"color":"#8a4cff","opacity":1}]}']),
        # H50 (painting phase 1): the brush panel beside the rail; Edit brush › (every setting); painting with nothing
        # selected (a new drawing); a long layer name in "Painting on"
        ("brush-panel", ["--sample"], ["select card", "flyout brush"]),
        ("brush-edit", ["--sample"], ["select card", "tool draw", "brushedit on"]),
        ("paint-new-drawing", ["--sample"], ["tool draw"]),
        # H51: each shape kind's own settings (a star, an arrow drawn start to end); the picture fill's picker;
        # the gradient's canvas handles with the picker open
        ("shape-star", ["--sample"], ["shape star 700 300 1000 600"]),
        ("shape-arrow", ["--sample"], ["shape arrow 600 700 1100 500"]),
        ("fill-picture-picker", ["--sample"], ["shape star 700 300 1000 600", "clickobj swatch", "clickobj fillType:picture",
                                               f"picturefile {PICTURE}", "clickobj picturePaint:fit 0.62 0.5"]),
        ("fill-gradient-handles", ["--sample"], ["shape star 700 300 1000 600", "clickobj swatch", "clickobj fillType:linear"]),
        ("paint-long-target", long(), [*busy, "select card", "tool draw"]),
        # H52 (painting phase 2): Draw each frame on, three drawings on twos, the onion skin's Before / After rows, the
        # cells on the timeline
        ("draw-each-frame", ["--sample"], [*FRAMES, "onion on", "frame prev"]),
        ("move-frame-layer", ["--sample"], [*FRAMES, "tool move"]),   # H61: the drawing's frame rows in the Move panel
        # H59: the drawing keyed where its drawings start and inside one: cells and key dots never cross, at any size
        ("draw-each-frame-keys", ["--sample"], [*FRAMES, "time 0", "keyhere", "time 0.0667", "set x 10", "time 0.5",
                                                "set x 20", "time 1", "set x 40", "onion on", "time 0.07"]),
        # H58: paint layers shared by all drawings: "Colour" added below "Paint", then 3 drawings with the same two layers
        ("paint-layers-shared", ["--sample"], ["tool draw", "draw 300 300 500 320 700 300", "paintlayer",
                                               'paintset paint_2 name "Colour"', "paintmove paint_2 1",
                                               "draw 320 340 520 360 720 340", "newframe", "draw 320 320 520 340 720 320",
                                               "newframe copy", "draw 340 340 540 360 740 340"]),
        ("draw-each-frame-long", long(), [*busy, "tool draw", "draw 300 300 500 320 700 300", *FRAMES[2:], "onion on"]),
        # H53: an ink brush adds Steadiness to the quick rows, beside Draw each frame's rows (the longest brush panel)
        ("draw-ink-brush", ["--sample"], [*FRAMES, "preset brushpen", "onion on"]),
        # H54: the drawing layer's name in full (no note beside it), empty frames' "+", a tick per frame; the Tip picture
        # list with Load picture…; a picture fill's thumbnail; a gradient with its own length (Cover the whole shape
        # again); the camera's Ride rows
        ("draw-empty-frames", ["--sample"], ["time 0.5", *FRAMES]),
        ("brush-edit-tip-list", long_project(), ["select card", "tool draw", "brushedit on", "clickobj row:texture 0.8 0.5"]),
        ("fill-picture-swatch", ["--sample"], ["shape star 700 300 1000 600", f'set paint {{"type":"picture","picture":"{PICTURE}"}}']),
        ("fill-gradient-own-length", ["--sample"], ["shape star 700 300 1000 600", 'set paint {"type":"linear","angle":90,'
                                                    '"span":"points","x1":0.2,"y1":0.5,"x2":0.6,"y2":0.5,"stops":[{"at":0,'
                                                    '"color":"#ff7a59","opacity":1},{"at":1,"color":"#101820","opacity":1}]}',
                                                    "clickobj swatch"]),
        ("camera-ride", ["--sample"], ["tool pen", "pen 300,300 900,500 1500,300", "tool move", "select path_1",
                                       "add camera", 'set ridePath "path_1"', "group Ride"]),
        ("library-brand", long_project(), ["select title_card_for_the_summer_launch_film", "do layer:style_save",
                                           "brand colors Summer_launch_coral_for_the_headphones_campaign #ff7a59",
                                           "brand colors Night #101820",
                                           f"brand textStyles {LONG_LAYER.replace(' ', '_')} textstyle_1", "library open"]),
            # H56: My brushes (a saved brush with a long name, chosen), Save this brush's name field on Edit brush ›
        ("brush-panel-mine", long_project(), ["select title_card_for_the_summer_launch_film", "tool draw", "preset oil",
                                              "savebrush Bristle_oil_for_the_night_sky_backgrounds", "preset chalk",
                                              "savebrush Soft_pastel", "flyout brush"]),
        ("brush-edit-save-name", long_project(), ["select title_card_for_the_summer_launch_film", "tool draw", "brushedit on",
                                                  "clickobj saveBrush"]),
        # H57: My brushes from the project and the person's library: one only in the project (long name, "project"),
        # one only in the library ("library"), one in both (no mark); a brush's right-click menu; a paint layer's
        ("brush-mine-places", long_project(), ["select title_card_for_the_summer_launch_film", "tool draw", "preset oil",
                                               "savebrush Bristle_oil_for_the_night_sky_backgrounds", "preset chalk",
                                               "savebrush Charcoal_rough", "preset air", "savebrush Air_soft",
                                               "flyout brush", "clickobj mybrush_1 right", "clickobj menu:drop:library",
                                               "flyout brush", "clickobj mybrush_2 right", "clickobj menu:drop:project",
                                               "flyout brush", "clickobj mybrush_2 right"]),
        ("paint-layer-menu", ["--sample"], [*PAINTED, "paintlayer", "draw 600 400 1200 420", "paintlayer", f"paintset {LONG_PAINT}",
                                            "clickobj paintLayer:Paint_2 right"]),
    ]
