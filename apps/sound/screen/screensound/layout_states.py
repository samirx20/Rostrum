"""RostrumSound's screen states for the layout check (rostrum_gui/layout_run.py): the empty song, the workspace with
the Editor, the Mixer or the Library open, the Export sheet, the open menus and dialogs, and the long-text
cases (a long song name, a long track name, many changes, a long status message).
A state is (name, start args, steps). Add one whenever a screen or panel is added."""
from __future__ import annotations

import tempfile
from pathlib import Path

from .layout_hem import LONG_MARKER, cues_song, two_songs
from .sample import SOURCE

LONG_TRACK = "lead_guitar_line_for_the_second_verse_and_bridge"
LONG_AGENT = "Claude: moved the title card, softened the door knock, and rebalanced the whole second verse against the drums"
LONG_STATUS = "No graphics driver, so drawing is slower"
LONG_SONG = "Summer_launch_film_for_the_new_headphones_-_final_score_v3"   # a step's words: _ for spaces
LONG_FOLDER = r"C:\Users\Sam\Music\Rostrum_deliveries\Summer_launch_film_for_the_new_headphones\final_score_round_three_for_the_client"
TWELVE = [f"select {LONG_TRACK}"] + [f"set volume {0.5 + n / 100}" if n % 2 else f"set pan {n / 100}" for n in range(12)]
GROUP = 'agent Group the band|[{{"op":"bus.from_tracks","target":["pad","melody","drums"],"args":{{"name":"{name}"}}}}]'
IGNORE = ()
SCRATCH = tempfile.TemporaryDirectory(prefix="rostrum-layout-")      # removed when the check run ends


def long_project() -> list[str]:
    """Start args for a saved song in a folder with a long name (a fresh folder each time)."""
    folder = Path(tempfile.mkdtemp(dir=SCRATCH.name)) / "Summer launch film for the new headphones - final score v3"
    script = folder.parent / "long_names.py"
    script.write_text(SOURCE.replace('track("melody"', f'track("{LONG_TRACK}"'), encoding="utf-8")
    return ["--doc", str(folder), "song", "--script", str(script)]


LAYERED = """tempo(100); beats_per_bar(4); length(bar(9))
hits = track("hits", volume=0.9)
hits.sound("click", at=2.0, group="a_long_layer_group_name_for_the_door_slam_in_the_second_scene")
hits.sound("hit", at=2.0, group="a_long_layer_group_name_for_the_door_slam_in_the_second_scene")
hits.sound("riser", at=1.5, dur=1.0, group="a_long_layer_group_name_for_the_door_slam_in_the_second_scene")
"""


def layered() -> list[str]:
    """Start args for a song whose designed sounds are layers of one group (a long group name)."""
    script = Path(tempfile.mkdtemp(dir=SCRATCH.name)) / "layered.py"
    script.write_text(LAYERED, encoding="utf-8")
    return ["--script", str(script)]


def states() -> list[tuple[str, list[str], list[str]]]:
    busy = [*TWELVE, f"say {LONG_STATUS}"]
    return [
        ("empty-song", ["--new"], []),
        ("editor", ["--sample"], ["dock editor", "select melody"]),
        ("mixer", ["--sample"], ["dock mixer", "select drums"]),
        ("library", ["--sample"], ["library"]),
        ("library-auditioning", ["--sample"], ["select melody", "library", "audition builtIn:grandPiano"]),
        ("library-trying-long", long_project(), [*busy, f"select {LONG_TRACK}", "library", "audition builtIn:grandPiano"]),   # P29: Keep / Revert
        ("clean-result-line", ["--sample"], ["select-clip door", "dock editor", "clean 0 0 1",
                                             "clean-line Background_noise_−18_dB_·_voice_level_−4_dB_·_room_echo_shorter|The_voice_got_quieter_too:_try_less."]),
        ("velocity-strip", ["--sample"], ["select melody", "dock editor", "velocity-line 0 0.2 6 1"]),
        ("key-shading", ["--sample"], ['agent Set the key|[{"op":"key.add","target":[],"args":{"at":0,"key":"D minor"}}]', "select melody", "dock editor"]),
        ("key-out-of-key-dots", ["--sample"], ['agent Set the key|[{"op":"key.add","target":[],"args":{"at":0,"key":"F# major"}}]', "select melody", "dock editor"]),
        ("velocity-strip-drums", ["--sample"], ["select drums", "dock editor"]),
        ("velocity-folded", ["--sample"], ["select melody", "dock editor", "vel-fold"]),
        ("group-open", ["--sample"], [GROUP.format(name="Band")]),
        ("group-muted-soloed", ["--sample"], [GROUP.format(name=LONG_TRACK), "group-toggle bus_1 mute", "group-toggle bus_1 solo"]),
        ("group-track-out", ["--sample"], [GROUP.format(name="Band"), "group-drop door bus_1", "group-drop melody door"]),
        ("group-folded", ["--sample"], [GROUP.format(name=LONG_TRACK), "fold bus_1"]),
        ("designed-layers", layered(), ["dock editor", "select hits.click2000"]),
        ("timeline-zoomed", ["--sample"], ["zoom 4 0.5"]),
        ("draw", ["--sample"], ["select melody", "dock editor", "tool draw"]),
        ("voice-lines", ["--sample"], ["add-track voice:ryan", "dock editor"]),
        ("voice-typed-lines", ["--sample"], ["add-track voice:ryan", "dock editor", "line-type Welcome to the show",
                                              "line-type And now, the news from the whole second verse and bridge"]),
        ("voice-model-question", ["--sample"], ["add-track voice:ryan", "dock editor", "line-type Welcome to the show", "voice-model-panel"]),   # P29: the download question
        ("voice-lane-typing", ["--sample"], ["add-track voice:ryan", "dock editor", "line-box 2"]),
        ("clean-before-after", ["--sample"], ["select-clip door", "dock editor", "clean 0 0 1"]),
        ("grid-menu", ["--sample"], ["grid-open"]),
        ("export", ["--sample"], ["deliver streaming", "export-open"]),
        ("long-export", long_project(), [*busy, "deliver streaming", "export-open"]),
        ("export-sheet", long_project(), [*busy, "exportsheet open streaming", f"exportwhere {LONG_FOLDER}"]),   # S34: the kit sheet
        ("export-versions", long_project(), [*busy, "range 1 3", "exportsheet open streaming", "export-what range",
                                             "export-more podcast mp3", "export-more ebu flac"]),     # P28: What + two more versions
        ("export-for-the-editor", ["--sample"], [GROUP.format(name="Music"), "exportsheet open streaming", "export-preset editor"]),   # P29: preset, stems by group
        ("swap-stepping", ["--sample"], ["select-clip door", "swap-demo", "swap-step 1", "swap-step 1"]),                    # P29: Trying in place
        ("problems-chip", long_project(), [*busy, "problems-demo", "problems open"]),
        ("job-chip", long_project(), [*busy, "job-show 42"]),
        ("long-editor", long_project(), [*busy, "dock editor"]),
        ("long-mixer", long_project(), [*busy, "dock mixer"]),
        ("long-library", long_project(), [*busy, "library"]),
        ("file-menu", long_project(), [*busy, "file-menu"]),
        ("start-screen", long_project(), [f"duplicate {LONG_SONG}_{n}" for n in (2, 3)] + ["startscreen open"]),   # long recent names
        ("song", ["--sample"], ["song-open"]),
        ("history-agent-run", ["--sample"], ["agent-run 6", "history open"]),
        ("agent-chip-long", long_project(), [*busy, "agent-run 3", f"agent-say {LONG_AGENT}"]),
        ("settings", ["--sample"], ["settings"]),
        ("commands", ["--sample"], ["commands"]),
        ("help-menu", ["--sample"], ["help"]),
        ("about", ["--sample"], ["about"]),
        ("connect-agent", ["--sample"], ["agents"]),
        ("guide", ["--sample"], ["guide first-song.md"]),
        ("guides-list", ["--sample"], ["guides open"]),                       # the kit's guides drawer (F1)
        ("guides-find", ["--sample"], ["guides find a_word_no_guide_has_anywhere_in_its_text_at_all"]),
        ("key-list", ["--sample"], ["keylist open"]),                          # Ctrl+/
        ("panels-folded", ["--sample"], ["panels fold"]),                      # Ctrl+\
        ("main-mix-offer", two_songs(SCRATCH.name, "beta"), []),                                # P30: "Make this the main mix"
        ("main-mix-marked", two_songs(SCRATCH.name, "alpha"), []),                              # P30: it is the main mix
        ("main-mix-made", two_songs(SCRATCH.name, "beta"), ["action main_mix"]),                # P30: after the action
        ("cues-from-2d", cues_song(SCRATCH.name), []),                                          # P30: the cue track, tagged clips
        ("cues-from-2d-selected", cues_song(SCRATCH.name), ["select cue_logo", "dock editor"]),
        ("cues-from-2d-long", cues_song(SCRATCH.name, LONG_MARKER.replace("_", " ")), ["select cue_logo"]),
        ("rename-name", long_project(), ["name edit"]),                       # S35: the name clicked, the kit's rename field
        # S48: the selection's actions at the top of the settings panel, and the one short right-click menu
        ("actions-clip", ["--sample"], ["select-clip door", "clean-open"]),
        ("actions-notes", ["--sample"], ["select melody", "dock editor", "select-many melody.n9600 melody.n10200 melody.n10800",
                                         "menu-roll melody.n10200"]),
        ("actions-tracks", ["--sample"], ["select-many pad melody", "menu melody"]),
        ("actions-range", ["--sample"], ["range 2 4"]),
        ("actions-marker-ask", ["--sample"], ["marker-add", "ask fit_bar"]),
    ]
