"""RostrumSound's operation modules and agent tool modules, in registration order (the order agents see them): the lists
the document kind and the agent server read (rostrum_core.modules). A plugin adds its own module to the same lists."""
from rostrum_core.modules import ModuleList

OPS = ModuleList("rostrum_sound.doc", [      # each registers its operations when imported
    ".ops_bus_tracks", ".ops_buses", ".ops_cleanup", ".ops_mix", ".ops_music", ".ops_range", ".ops_fit", ".ops_section_copy", ".ops_select_clips",
    ".ops_select_move", ".ops_select_notes", ".ops_select_place", ".ops_select_tracks", ".ops_swap", ".ops_timed", ".ops_tracks", ".ops_listen", ".ops_plugin_items", ".ops_transpose", ".ops_thin",
    ".ops_fit_key", ".ops_feel", ".ops_fill", ".ops_voice", ".ops_chord", ".ops_strum", ".ops_pedal", ".ops_ramp", ".ops_arp", ".ops_carry",
])

TOOLS = ModuleList("rostrum_sound.mcp", [   # each has `register(tools)`
    ".tools_render", ".tools_audition", ".tools_look", ".tools_arrangement", ".tools_inspect", ".tools_sfx", ".tools_voice", ".tools_motion",
    ".tools_plugins", ".tools_midi", ".tools_cleanup", ".tools_ears", ".tools_project", ".tools_main_mix", ".tools_notes", ".tools_note_diff", ".tools_history_go",
])
