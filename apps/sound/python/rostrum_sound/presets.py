"""Delivery presets: a named set of the render's choices, for where the files are going (data, not taste: each says
exactly what it sets). A request's own choices win over a preset's.

    "editor": for the Rostrum Editor (and any video editor), as DESIGN.md §10 #10 sets it: WAV 48 kHz 32-bit float
    (video's rate; no rounding, so the final mix happens in the Editor), the mix before mastering (no loudness change:
    the Editor's final mix sets the loudness), and one stem per group (groups named Dialogue / Music / Effects give shared/HANDOFFS.md's split), the song's
    full length (no trimming, so every file starts together and ends together with the picture), and the named markers
    written beside the files as `markers.json` (handoff.write_markers), so the Editor syncs to "logo lands" by name.
"""
from __future__ import annotations

PRESETS = {
    "editor": {"label": "For the Editor", "detail": "WAV 48 kHz 32-bit float, no loudness change, the mix and a stem per group, markers beside them",
               "format": "wav32f", "sampleRate": 48000, "trim": False, "master": False, "stems": "groups", "markers": True},
}


def expand(args: dict, name: str | None) -> dict:
    """`args` with the preset's choices filled in where the request made none."""
    if not name:
        return dict(args)
    if name not in PRESETS:
        from rostrum_core import RostrumError, codes
        raise RostrumError(codes.BAD_ARGUMENT, "render", f'preset "{name}"', "is not one we have",
                           hint="Use one of: " + ", ".join(PRESETS) + ".")
    p = PRESETS[name]
    return {**{k: v for k, v in p.items() if k not in ("label", "detail")}, **args}
