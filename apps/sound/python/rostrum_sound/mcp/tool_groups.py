"""The Sound server's tools, few and clear (CONVENTIONS § 2): tools that answer the same kind of question are one tool, and
`what` picks the question. Each part is still written as its own small tool in its own module; this list joins them.
An old name answers with an error naming the tool and the `what` to pass (rostrum_core.mcp.combine)."""
from __future__ import annotations

from rostrum_core.mcp.combine import combine

GROUPS = [
    ("look_sound", "Hear the mix as numbers and pictures; opens NOT DONE: (faults: time, fix) or DONE:.",
     {"loudness": "look_loudness", "levels": "look_levels", "spectrum": "look_spectrum", "stereo": "look_stereo",
      "low_end": "look_low_end", "clash": "look_clash", "cleanup": "look_cleanup"}, "loudness"),
    ("look_music", "Hear the music as facts.",
     {"events": "look_events", "beats": "look_beats", "pitch": "look_pitch", "harmony": "inspect_harmony"}, "events"),
    ("inspect_engine", "What the sound engine can play.",
     {"names": "inspect_engine", "instrument": "inspect_instrument", "plugins": "inspect_plugins"}, "names"),
    ("inspect_library", "Sound files to use (inspect_guide 'library').",
     {"sounds": "inspect_library", "cuts": "inspect_cuts"}, "sounds"),
    ("render_voice", "Voice lines.",
     {"takes": "render_voice", "words": "render_voice_words", "estimate": "render_voice_estimate"}, "takes"),
    ("render_mix", "Render the song (a job). Under the loudness target: edit_loudness {\"apply\": \"best\"}.",
     {"mix": "render_mix", "midi": "render_midi"}, "mix"),
    ("run_open_project", "The person's songs.",
     {"open": "run_open_project", "recent": "inspect_recent_projects"}, "open"),
]

CORE = ["run_script", "look_sound", "look_music", "inspect_guide", "render_mix"]


def group(tools):
    """Join the parts in place; returns `tools`."""
    for name, lead, parts, default in GROUPS:
        combine(tools, name, lead, parts, default=default)
    tools.core = list(CORE)
    return tools
