"""The Sound server's tools, few and clear (CONVENTIONS § 2): tools that answer the same kind of question are one tool, and
`what` picks the question. Each part is still written as its own small tool in its own module; this list joins them.
An old name answers with an error naming the tool and the `what` to pass (rostrum_core.mcp.combine)."""
from __future__ import annotations

from rostrum_core.mcp.combine import combine

GROUPS = [
    ("look_sound", "Hear the mix as numbers and pictures: loudness and clipping (default), each track's level, a "
     "spectrogram, stereo balance, the low end, where one stem buries another, or what a clip's clean-up did. Use "
     "\"loudness\" before delivering, \"levels\" / \"low_end\" / \"clash\" to balance a mix (they read the last render's stems).",
     {"loudness": "look_loudness", "levels": "look_levels", "spectrum": "look_spectrum", "stereo": "look_stereo",
      "low_end": "look_low_end", "clash": "look_clash", "cleanup": "look_cleanup"}, "loudness"),
    ("look_music", "Hear the music as facts: where sounds start and whether they hit their times (default), the tempo "
     "and beat grid, the pitch of a melodic line against the written notes, or the key and chords.",
     {"events": "look_events", "beats": "look_beats", "pitch": "look_pitch", "harmony": "inspect_harmony"}, "events"),
    ("inspect_engine", "What the sound engine can play: every name it accepts and which built-in sound suits which part "
     "(default), one instrument's range and drum names, or the installed CLAP / VST3 plug-ins.",
     {"names": "inspect_engine", "instrument": "inspect_instrument", "plugins": "inspect_plugins"}, "names"),
    ("inspect_library", "Sound files to use: installed packs and the person's own sound folders, searched by words, kind "
     "and shape (default), or recordings cut into single sounds (the cut pool).",
     {"sounds": "inspect_library", "cuts": "inspect_cuts"}, "sounds"),
    ("render_voice", "Voice lines: make the missing takes (default), or find each spoken word's start and end.",
     {"takes": "render_voice", "words": "render_voice_words"}, "takes"),
    ("render_mix", "Render the song: the mix and its stems as the next version (default), or the notes as a MIDI file.",
     {"mix": "render_mix", "midi": "render_midi"}, "mix"),
    ("run_open_project", "The person's songs: open one (default; every change is already saved, so nothing is lost), "
     "or list the recent ones to pick from.",
     {"open": "run_open_project", "recent": "inspect_recent_projects"}, "open"),
]


def group(tools):
    """Join the parts in place; returns `tools`."""
    for name, lead, parts, default in GROUPS:
        combine(tools, name, lead, parts, default=default)
    return tools
