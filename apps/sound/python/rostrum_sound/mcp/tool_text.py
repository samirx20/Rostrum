"""What the agent reads in the tool list: one short sentence per tool (part) and short argument words (CONVENTIONS § 2: a
tool's description at most 150 words). Each part's own docstring and argument texts stay the full account: they make the
guide page `tools-in-detail` (every part, every argument), so moving the words here loses nothing. The helpers are
rostrum_core.mcp.short_text (shared with 2D and 3D).

`shorten(tools)` runs on the parts before tool_groups joins them, so a joined tool pastes these short sentences."""
from __future__ import annotations

from rostrum_core.mcp import short_text

# One sentence per part: what it is for, when to pick it. A part not listed keeps its own text.
SAY = {
    # look_sound's parts
    "look_loudness": "Loudness, peaks, ending and faults; before delivering.",
    "look_levels": "Each track's level and who drives the limiter.",
    "look_spectrum": "A spectrogram, steady tones and hum.",
    "look_stereo": "Stereo balance per section.",
    "look_low_end": "Each track's low end and low mids.",
    "look_clash": "Where one stem buries another.",
    "look_cleanup": "A clip's clean-up, before vs after.",
    # look_music's parts
    "look_events": "Where sounds start; with `expect`, whether each moment lands.",
    "look_beats": "Tempo, beat grid and swing.",
    "look_pitch": "A track's written notes against what sounds.",
    "inspect_harmony": "Key, chords and voicing checks, from the written notes.",
    # inspect_engine's parts
    "inspect_engine": "Every playable name; `name` for one thing's settings.",
    "inspect_instrument": "One instrument's range or a kit's drums (one of builtIn, model, synth, sfz, kit, kitSfz).",
    "inspect_plugins": "Installed CLAP / VST3 plug-ins.",
    # inspect_library's parts
    "inspect_library": "Sample packs and the person's sound folders, searched.",
    "inspect_cuts": "Recordings cut into single sounds.",
    # render_voice's parts
    "render_voice": "Make the missing voice takes.",
    "render_voice_words": "Each spoken word's start and end.",
    "render_voice_estimate": "How long lines will take, before making them.",
    # render_mix's parts
    "render_mix": "The next mix and stems, listened to; open faults need `keep`.",
    "render_midi": "The notes as a MIDI file.",
    # run_open_project's parts
    "run_open_project": "Open a project folder (made when new).",
    "inspect_recent_projects": "The person's recent songs.",
    # tools on their own
    "edit_loudness": "When reaching the loudness target took heavy limiting: measured ways to need less, each with ready ops; `apply` makes one (a job): {\"apply\": \"best\"}.",
    "render_audition": "Hear an instrument, kit, file or a track's notes as a short WAV; the song is unchanged.",
    "look_arrangement": "The written song as a picture (tracks, bars, sections, markers) and who starts on each marker; no render.",
    "inspect_diagnose": "Everything broken in a song (missing files, past the end, out of range …), each with its fix.",
    "look_video": "The picture the sound is for: frames, a contact sheet, or motion with sudden stops.",
    "edit_sounds_from_motion": "Musical answers to a 2D motion export's moments; adds only what `add` names.",
    "edit_import_midi": "Import a MIDI file as tracks, lanes, markers and (song_map) the tempo map.",
    "render_cleanup": "Make the missing cleaned takes of the clips; then look_sound what cleanup.",
    "run_model_install": "Download a model or sample pack a tool needs (checked by its fingerprint).",
    "run_set_main_mix": "Make a song the project's main mix (the one 2D plays with the picture).",
    "inspect_notes": "A track's notes and hits in a stretch, with their ids.",
    "inspect_note_changes": "What happened to the notes between two states of the song.",
    "edit_history_go": "Stand at the song right after history step `to` (your own steps only).",
}

# Argument words, by name, for every part that has the argument (the same words let tool_groups show them once).
ARG = {
    "item": "Song id (optional with one open).",
    "wait": "Wait: true (50 s) or seconds.",
    "wav": "A WAV instead of the last render.",
    "track": "One track's stem instead of the mix.",
    "start": "From here (a time); needs end.",
    "end": "To here.",
    "detail": "short or full lists.",
    "expect": "Times, or {at, kind: hit|stop|drop|climax|lift|entry|voice}, or {kind: tempo, bpm}.",
    "ids": "Only these ids; default all.",
    "limit": "At most this many rows.",
    "tolerance": "Seconds a sound may be off.",
    "find": "Words to match.",
    "seconds": "[low, high]; either may be null.",
    "attack_ms": "[low, high]; either may be null.",
    "lufs": "[low, high]; either may be null.",
    "section": "A section's name.",
    "from": "From here (a time).",
    "to": "To here (not included).",
}

# Where one part's argument needs its own words (the same name means something else in another part).
ARG_OF = {
    ("look_spectrum", "marks"): "Labels at times: {\"hit\": 12.5}.",
    ("look_stereo", "section"): "Seconds per section.",
    ("look_clash", "tracks"): "Only these stems (up to 12).",
    ("look_clash", "within_db"): "Both loud and within this many dB.",
    ("look_clash", "floor_db"): "Band level under which a stem is absent.",
    ("look_clash", "min_over_db"): "Only where one stands this many dB over.",
    ("look_clash", "min_length"): "Shortest clash, s.",
    ("look_cleanup", "clip"): "A clip id: its file vs its cleaned take.",
    ("look_cleanup", "before"): "A WAV before cleanup.",
    ("look_cleanup", "after"): "The same WAV after.",
    ("look_cleanup", "stems"): "{name: WAV path}: leakage check.",
    ("look_cleanup", "reference"): "{name: WAV path}: true parts.",
    ("look_events", "by_stem"): "Which stem starts nearest each time.",
    ("look_beats", "stems"): "Every stem's onsets too.",
    ("look_beats", "beats_per_bar"): "For the downbeat; default the song's.",
    ("look_beats", "division"): "4 sixteenths, 2 eighths, 1 beats.",
    ("look_pitch", "fmin"): "Lowest pitch, Hz.",
    ("look_pitch", "fmax"): "Highest pitch, Hz.",
    ("look_pitch", "cents_tolerance"): "Cents a note may be off.",
    ("look_pitch", "timing_tolerance"): "Seconds a note may be early or late.",
    ("inspect_harmony", "source"): "auto: written notes if any, else audio.",
    ("inspect_harmony", "key"): "Check against this key (\"D minor\").",
    ("inspect_harmony", "checks"): "Voicing checks on the written notes.",
    ("inspect_engine", "name"): "One effect, space, master, instrument or kit.",
    ("inspect_engine", "detail"): "full: everything (about 50 KB).",
    ("inspect_instrument", "builtIn"): "A plain name (piano, warmPad …).",
    ("inspect_instrument", "model"): "A modelled instrument (guitar, violin …).",
    ("inspect_instrument", "synth"): "A synth wave.",
    ("inspect_instrument", "sfz"): "An .sfz file path.",
    ("inspect_instrument", "kit"): "drums, studio, jazz or classic.",
    ("inspect_instrument", "kitSfz"): "An SFZ drum kit path.",
    ("inspect_plugins", "path"): "A plug-in file or folder to scan.",
    ("inspect_plugins", "params"): "List each plug-in's parameters.",
    ("inspect_library", "kind"): "packs, instruments, recordings, sounds or a sound kind.",
    ("inspect_library", "folder"): "One of the person's sound folders.",
    ("inspect_library", "length"): "short < 0.5 s, medium < 1.5 s, long.",
    ("inspect_library", "attack"): "sharp < 15 ms, soft > 60 ms.",
    ("inspect_library", "brightness_range"): "[low, high], 0 (250 Hz) … 1 (8 kHz).",
    ("inspect_cuts", "recordings"): "Recordings to cut (paths).",
    ("inspect_cuts", "mode"): "hits or beds.",
    ("render_voice_words", "read_only"): "Only read stored words.",
    ("render_voice_estimate", "text"): "Words to estimate without a line.",
    ("render_voice_estimate", "language"): "With text: its language.",
    ("render_mix", "solo"): "Only these tracks heard.",
    ("render_mix", "mute"): "These tracks not heard.",
    ("render_mix", "master"): "False: before mastering.",
    ("render_mix", "stems"): "A file per track and group; groups; false.",
    ("render_mix", "preset"): "editor: 48 kHz float, group stems, markers.",
    ("render_mix", "format"): "wav24 video, wav16 CD, wav32f, flac, mp3.",
    ("render_mix", "sampleRate"): "Hz; default the song's.",
    ("render_mix", "trim"): "Stop at the last audible sound.",
    ("render_mix", "from"): "Only a part, from here; needs to.",
    ("render_mix", "to"): "The part's end.",
    ("render_mix", "name"): "File name without its type.",
    ("render_midi", "name"): "File name without its type.",
    ("render_mix", "folder"): "Also copy the files to this folder.",
    ("render_mix", "expect"): "Moments to check; default hit-like markers.",
    ("render_mix", "keep"): "Faults left on purpose: {id: why}.",
    ("render_mix", "ring_past_length"): "Ring out past the length.",
    ("render_midi", "path"): "Where to write the .mid.",
    ("run_open_project", "folder"): "The project folder (absolute; made when new).",
    ("run_open_project", "item"): "The song; default the recent or newest one.",
    ("edit_loudness", "track"): "The track to tame or lower.",
    ("edit_loudness", "apply"): "Apply this option as one change.",
    ("render_audition", "entry"): "{instrument: builtIn, builtIn: \"cello\"}, {instrument: kit, kit} or {media: path}.",
    ("render_audition", "track"): "Play this track's own notes.",
    ("render_audition", "from"): "Seconds to take the notes from.",
    ("render_audition", "bars"): "How many bars.",
    ("look_arrangement", "start"): "Seconds to draw from.",
    ("look_arrangement", "end"): "Seconds to draw to.",
    ("look_video", "video"): "The picture's path.",
    ("look_video", "at"): "frames: the time to look around.",
    ("look_video", "span"): "frames: frames each side.",
    ("look_video", "every"): "sheet: seconds between tiles.",
    ("look_video", "min_confidence"): "motion: weakest stop kept (0 … 1).",
    ("edit_sounds_from_motion", "samples"): "2D's render_export motion JSON.",
    ("edit_sounds_from_motion", "add"): "\"<moment>:<answer>\" to write; empty: suggest only.",
    ("edit_sounds_from_motion", "key"): "The key (\"D minor\").",
    ("edit_sounds_from_motion", "glue"): "Route library tracks into the ui bus.",
    ("edit_sounds_from_motion", "detail"): "List every removed item.",
    ("edit_import_midi", "path"): "The .mid file.",
    ("edit_import_midi", "song_map"): "Also its tempo map, metre and keys.",
    ("run_model_install", "model"): "A model, or a sample pack (inspect_library kind packs).",
    ("inspect_notes", "track"): "The track's id.",
    ("inspect_notes", "from"): "Start: {\"bar\": 5}, {\"beat\": 8}, seconds or \"#drop\".",
    ("inspect_note_changes", "since"): "A step, {\"mine\": N}, {\"steps\": N} or {\"version\": name}.",
    ("inspect_note_changes", "until"): "A later step; default now.",
    ("inspect_note_changes", "track"): "Only this track.",
    ("inspect_note_changes", "from"): "Notes from here: {\"bar\": 5}, seconds, \"#drop\".",
    ("edit_history_go", "to"): "The step to stand at (0 = empty).",
}

MOST = 12        # argument words kept from a part's own text when neither table names it
PLAIN = {"item", "wait", "wav", "start", "end", "track", "detail"}   # said without the choices that take them (a wrong one is refused by name)


def shorten(tools):
    """Every part's short sentence and short argument words, in place; returns `tools`."""
    return short_text.shorten(tools, SAY, ARG, ARG_OF, MOST)


def tidy(tools, names):
    return short_text.tidy(tools, names, PLAIN)


def part_tools():
    """Every Sound tool as written, before the short words and the joining (their full text: guide 'tools-in-detail')."""
    from rostrum_core.mcp import Tools
    from ..modules import TOOLS
    tools = Tools()
    TOOLS.call("register", tools)
    return tools


def detail_page(tools) -> str:
    from . import tool_groups
    return short_text.detail_page(tools, tool_groups.GROUPS,
        "The full account of each Sound tool and each of its arguments: the exact numbers, defaults and edge cases. The "
        "tool list keeps one short sentence each; a joined tool (look_sound, look_music, render_mix, ...) is listed here "
        "per `what` choice. Start at inspect_guide 'start-here'.")
