"""Sound's own keys as data (INTERACTION.md Part 2, the [Sound] rows), for `KeyMap("Sound", SOUND_KEYS)`. Everything
else Sound uses (Space, Ctrl+G, Delete, arrows, F2 ...) is a shared key and comes from the shared map.
"""
SOUND_KEYS = [
    {"job": "record", "keys": ["R"], "label": "Record on the armed track", "area": "Play"},
    {"job": "click", "keys": ["Shift+K"], "label": "Click (metronome) on / off", "area": "Play"},
    {"job": "pitch_scale_up", "keys": ["Ctrl+Up"], "label": "Pitch up a scale step", "area": "Edit"},
    {"job": "pitch_scale_down", "keys": ["Ctrl+Down"], "label": "Pitch down a scale step", "area": "Edit"},
    {"job": "quantize", "keys": ["Q"], "label": "Quantise", "area": "Edit"},
    {"job": "next_take", "keys": ["T"], "label": "Next take", "area": "Edit"},
    {"job": "swap_sound", "keys": ["S"], "label": "Swap a sound", "area": "Edit"},
    {"job": "hear_original", "keys": ["H"], "label": "Hear the original (hold)", "area": "Edit"},
    {"job": "mute", "keys": ["Shift+M"], "label": "Mute", "area": "Edit"},
    {"job": "solo", "keys": ["Shift+S"], "label": "Solo", "area": "Edit"},
    {"job": "editor_dock", "keys": ["E"], "label": "Editor dock", "area": "Panels"},
    {"job": "mixer_dock", "keys": ["X"], "label": "Mixer dock", "area": "Panels"},
]
