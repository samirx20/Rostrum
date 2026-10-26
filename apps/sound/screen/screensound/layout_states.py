"""RostrumSound's screen states for the layout check (rostrum_gui/layout_run.py): the empty song, the workspace with
the Editor, the Mixer or the Library open, the Export sheet, the open menus and dialogs, and the long-text
cases (a long song name, a long track name, many changes, a long status message).
A state is (name, start args, steps). Add one whenever a screen or panel is added; name it in QUICK when it is one of
the most important (the quick check runs those)."""
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
# The most important states: `main.py --check-layout <folder> --quick` runs just these, at 1646x900 (Sam's screen), in
# about 2 minutes. Every brief runs it before reporting; the full run (every state, four sizes) stays for merges and audits.
BATCH = 1        # one state to a process: measured, Sound opens a song slower the more windows it has made (10 states
                 # batched took 95 s, one each 83 s); its time goes to opening the song and its steps, not to starting
QUICK = ("empty-song", "editor", "mixer", "master-selected", "library", "library-voice", "library-key-picture", "long-editor", "long-mixer", "long-library", "export-sheet", "solo-on", "export-solo", "file-menu",
         "start-screen", "song", "settings", "commands", "guide", "about", "group-open", "voice-lines", "clean-before-after",
         "grid-menu", "in-key-menu", "problems-chip", "feel-drums-swing", "amounts-humanize", "amounts-repeat-range", "marker-menu", "drum-row-fill-menu", "chord-menu")
SCRATCH = tempfile.TemporaryDirectory(prefix="rostrum-layout-")      # removed when the check run ends


SONG_FLAGS = ('agent Tempo glide, a 3/4 bar, 6/8 and a key|[{"op":"tempo.add","target":[],"args":{"at":{"beat":8},"bpm":100,"ramp":true}},'
              '{"op":"tempo.add","target":[],"args":{"at":{"beat":20},"bpm":132}},'
              '{"op":"meter.add","target":[],"args":{"at":{"beat":12},"beatsPerBar":3}},'
              '{"op":"meter.add","target":[],"args":{"at":{"beat":15},"beatsPerBar":6,"beatUnit":8}},'
              '{"op":"key.add","target":[],"args":{"at":{"beat":15},"key":"D minor"}}]')

PICTURE = 'agent A picture|[{"op":"doc.set","target":["root"],"args":{"picture":"film.mp4"}}]'   # its button shows (no file needed)
DKEY = 'agent A key|[{"op":"key.add","target":[],"args":{"at":0,"key":"D minor"}}]'
CHORD = ('agent A chord|[' + ",".join('{"op":"note.add","target":["melody"],"args":{"id":"%s","pitch":"%s","at":{"beat":16},"dur":{"beats":4}}}'
                                       % (i, p) for i, p in (("c1", "D4"), ("c2", "F4"), ("c3", "A4"))) + "]")
SIX_EIGHT = 'agent Song in 6/8|[{"op":"doc.set","target":["root"],"args":{"beatsPerBar":6,"beatUnit":8}}]'


def long_project() -> list[str]:
    """Start args for a saved song in a folder with a long name (a fresh folder each time)."""
    folder = Path(tempfile.mkdtemp(dir=SCRATCH.name)) / "Summer launch film for the new headphones - final score v3"
    script = folder.parent / "long_names.py"
    script.write_text(SOURCE.replace('track("melody"', f'track("{LONG_TRACK}"'), encoding="utf-8")
    return ["--doc", str(folder), "song", "--script", str(script)]


BEND = ('agent Bend the melody|[{"op":"automation.set","target":["melody"],"args":{"lane":"bend","points":'
        '[[0,0],[1.5,0],[2,0.5],[4,0.5],[4.5,0]]}}]')


# Sound pro workflows, workflow 5: a notes or drums track's Feel group (Swing, Played like a person and its amounts, More)
SWING = 'agent Swing the drums|[{"op":"track.feel","target":["drums"],"args":{"swing":0.55,"swingGrid":0.25}}]'


def feel_states() -> list[tuple[str, list[str], list[str]]]:
    return [
        ("feel-notes", ["--sample"], ["select melody"]),                                   # person on: Looseness, Velocity spread
        ("feel-drums-swing", ["--sample"], [SWING, "select drums"]),                      # Swing first, Swing on 16ths
        ("feel-more", long_project(), [f"select {LONG_TRACK}", "more"]),                  # Lean … Seed behind More, a long name
    ]


def states() -> list[tuple[str, list[str], list[str]]]:
    busy = [*TWELVE, f"say {LONG_STATUS}"]
    return [
        ("empty-song", ["--new"], []),
        ("editor", ["--sample"], ["dock editor", "select melody"]),
        ("mixer", ["--sample"], ["dock mixer", "select drums"]),
        ("master-selected", ["--sample"], ["dock mixer", "select master"]),          # the master's loudness and gentle limiting
        ("f11-track", ["--sample"], ["select melody"]),                         # F11: the track's settings panel
        ("f11-clip", ["--sample"], ["select-clip door"]),                       # F11: a clip's settings panel
        ("header-long-name-selected", long_project(), [f"select {LONG_TRACK}"]),               # B3: the name keeps its room, buttons stay put
        ("header-long-name-locked", long_project(), ["select drums", f"lock {LONG_TRACK}"]),    # B3: a padlock by the name, the unselected row
        ("library", ["--sample"], ["library"]),
        ("library-voice", ["--sample"], ["library voice"]),
        # the Library open on a song with a key and a picture: the strip's shortest case (critic r9 + r10: "Minor" ran
        # under the Picture button; the state with no key showed "No key", shorter, and missed it)
        ("library-key-picture", ["--sample"], [DKEY, PICTURE, "zoom 2", "library"]),
        ("library-auditioning", ["--sample"], ["select melody", "library", "audition builtIn:piano"]),
        ("library-hearing-long", long_project(), [*busy, f"select {LONG_TRACK}", "library", "audition builtIn:piano"]),   # P29: the Hearing line + Stop
        ("clean-result-line", ["--sample"], ["select-clip door", "dock editor", "clean 0 0 1",
                                             "clean-line Background_noise_−18_dB_·_voice_level_−4_dB_·_room_echo_shorter|The_voice_got_quieter_too:_try_less."]),
        ("velocity-strip", ["--sample"], ["select melody", "dock editor", "velocity-line 0 0.2 6 1"]),
        ("editor-playing-lane", ["--sample"], [BEND, "select melody", "dock editor", "play-lane bend"]),   # S56
        ("export-midi", long_project(), [*busy, "exportsheet open midi", f"exportwhere {LONG_FOLDER}"]),     # S56
        ("key-shading", ["--sample"], ['agent Set the key|[{"op":"key.add","target":[],"args":{"at":0,"key":"D minor"}}]', "select melody", "dock editor"]),
        ("key-out-of-key-dots", ["--sample"], ['agent Set the key|[{"op":"key.add","target":[],"args":{"at":0,"key":"F# major"}}]', "select melody", "dock editor"]),
        ("song-flags", ["--sample"], [SONG_FLAGS]),
        ("tempo-ramp-selected", ["--sample"], [SONG_FLAGS, "select tempo_1"]),       # S54: the ramp toggle in the inspector
        ("six-eight-selected", ["--sample"], [SONG_FLAGS, SIX_EIGHT, "select meter_2"]),   # S55: 6/8 header, flag, beat unit
        ("velocity-strip-drums", ["--sample"], ["select drums", "dock editor"]),
        ("velocity-folded", ["--sample"], ["select melody", "dock editor", "vel-fold"]),
        ("group-open", ["--sample"], [GROUP.format(name="Band")]),
        ("group-muted-soloed", ["--sample"], [GROUP.format(name=LONG_TRACK), "group-toggle bus_1 mute", "group-toggle bus_1 solo"]),
        ("group-track-out", ["--sample"], [GROUP.format(name="Band"), "group-drop door bus_1", "group-drop melody door"]),
        ("group-folded", ["--sample"], [GROUP.format(name=LONG_TRACK), "fold bus_1"]),
        ("timeline-zoomed", ["--sample"], ["zoom 4 0.5"]),
        ("draw", ["--sample"], ["select melody", "dock editor", "tool draw"]),
        ("voice-lines", ["--sample"], ["add-track voice:ryan", "dock editor"]),
        ("voice-typed-lines", ["--sample"], ["add-track voice:ryan", "dock editor", "line-type Welcome to the show",
                                              "line-type And now, the news from the whole second verse and bridge"]),
        ("voice-model-question", ["--sample"], ["add-track voice:ryan", "dock editor", "line-type Welcome to the show", "voice-model-panel"]),   # P29: the download question
        ("voice-lane-typing", ["--sample"], ["add-track voice:ryan", "dock editor", "line-box 2"]),
        ("clean-open", ["--sample"], ["select-clip door", "dock editor", "clean-open"]),            # F16: the three controls once
        ("clean-before-after", ["--sample"], ["select-clip door", "dock editor", "clean 0 0 1"]),
        ("grid-menu", ["--sample"], ["grid-open"]),
        # In key ▾ (SPEC 3.6): the chip's menu on a notes track in a song with a key, Keep on; and the roll with only the key's rows
        ("in-key-menu", ["--sample"], [DKEY, "select melody", "dock editor", "inkey keep", "inkey-open"]),
        ("fit-to-key", ["--sample"], [DKEY, 'agent A note outside the key|[{"op":"note.add","target":["melody"],"args":{"id":"out","pitch":"C#4","at":{"beat":0},"dur":{"beats":1}}}]',
                                       "select out", "dock editor"]),         # Fit to key leads the panel's actions
        ("note-draw-menu", ["--sample"], [DKEY, "select melody", "dock editor", "note-open"]),      # Note ▾: length, then Draw (Chord in key present)
        ("in-key-rows", ["--sample"], [DKEY, "select melody", "dock editor", "inkey rows"]),
        ("export", ["--sample"], ["deliver streaming", "export-open"]),
        ("long-export", long_project(), [*busy, "deliver streaming", "export-open"]),
        ("solo-on", ["--sample"], ["solo melody", "select drums"]),                        # the top bar's "Solo on: …" chip, a lit S
        ("solo-on-long", long_project(), [f"solo {LONG_TRACK}", "mute drums"]),            # a long name in the chip
        ("export-solo", ["--sample"], ["solo melody", "mute drums", "exportsheet open streaming"]),   # the sheet warns: solo, mute, one click
        ("export-sheet", long_project(), [*busy, "exportsheet open streaming", f"exportwhere {LONG_FOLDER}"]),   # S34: the kit sheet
        ("export-versions", long_project(), [*busy, "range 1 3", "exportsheet open streaming", "export-what range",
                                             "export-more podcast mp3", "export-more ebu flac"]),     # P28: What + two more versions
        ("export-range", long_project(), [*busy, "range 1 3", "exportsheet open streaming", "export-what range",
                                          f"exportwhere {LONG_FOLDER}"]),     # a range chosen: its own loudness check, one line
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
        ("two-tracks-mixed", ["--sample"], ["select-many pad melody"]),               # S49: "Mixed" in a unit field, no unit over it
        ("actions-audio-clip-menu", ["--sample"], ["select-clip door", "menu door/clip"]),     # Split here, Fades, Swap…
        ("actions-range", ["--sample"], ["range 2 4"]),
        ("actions-marker-ask", ["--sample"], ["marker-add", "ask fit_bar"]),
        ("marker-menu", ["--sample"], ["time 4", "marker-add", "rename hit", "time 1", "marker-menu hit"]),   # the kit's
                                                                             # marker menu: Sound's rows, Loop to "drop"               # Start a bar here…: the kit's amounts popover
        # the amounts popover (kit base A): Humanise ▾, Quantise ▾ with More open, Transpose ▾ › By… along the key, Repeat…
        ("amounts-humanize", ["--sample"], ["select melody", "dock editor", "select-many melody.n9600 melody.n10200 melody.n10800",
                                            "ask humanize"]),
        ("amounts-quantize-more", ["--sample"], ["select melody", "dock editor", "select-many melody.n9600 melody.n10200",
                                                 "ask quantize", "amount swing 0.5"]),
        ("amounts-transpose-key", ["--sample"], [SONG_FLAGS, "select melody", "dock editor",
                                                 "select-many melody.n9600 melody.n10200", "ask transpose_by", "amount along 1"]),
        # Chord ▾ (SPEC 3.9–3.11) on three notes of a chord in a song with a key: its menu with Make a chord ▸ open; Strum…, Arpeggio…
        ("chord-menu", ["--sample"], [DKEY, CHORD, "select melody", "dock editor", "select-many c1 c2 c3", "bar-menu Chord Make_a_chord"]),
        ("amounts-strum", ["--sample"], [DKEY, CHORD, "select melody", "dock editor", "select-many c1 c2 c3", "ask strum"]),
        ("amounts-arpeggio", ["--sample"], [DKEY, CHORD, "select melody", "dock editor", "select-many c1 c2 c3", "ask arpeggio"]),
        # a drum row's name menu (SPEC 3.8): Hear, Select all, Fill ▸ (open), Clear, Change drum ▸; Fill row… in the amounts popover
        ("drum-row-menu", ["--sample"], ["dock editor", "select drums", "drum-menu hat"]),
        ("drum-row-fill-menu", ["--sample"], ["dock editor", "select drums", "drum-fill-menu hat"]),
        ("amounts-fill-row", ["--sample"], ["dock editor", "select drums", "drum-fill-row hat"]),
        ("amounts-repeat-range", ["--sample"], ["range 2 4", "ask repeat_range"]),
        ("amounts-repeat-notes", ["--sample"], ["select melody", "dock editor", "select-many melody.n9600 melody.n10200",
                                                "ask repeat", "amount until #drop"]),
        # P41: the full transport (loop on, a track armed), times in bars.beats, the Mixer with an effect selected
        ("transport-loop-armed", ["--sample"], ["time 9", "loop", "arm door"]),
        ("note-musical-times", ["--sample"], ["dock editor", "select melody.n9600"]),
        ("six-eight-note", ["--sample"], [SONG_FLAGS, SIX_EIGHT, "dock editor", "select melody.n9600"]),
        ("mixer-effect", ["--sample"], ['agent Add a delay|[{"op":"effect.add","target":["drums"],"args":{"effect":"delay"}}]',
                                        "dock mixer", "select drums.delay_1"]),
        *feel_states(),
    ]
