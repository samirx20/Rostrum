"""What the Export sheet offers for stems and delivery presets (no Qt). Stems: only the mix, a file for every track and
group, or a file per group with the tracks in no group each their own (`render_mix {stems: "groups"}`, stem_groups.py);
the last is offered only when the song has a group (a bus that tracks play into). A preset ("For the Editor",
presets.py) is a button that sets the sheet's choices; it shows as chosen while the sheet still matches it.
"""
from __future__ import annotations

from rostrum_sound import presets
from rostrum_sound.stem_groups import routed_to_master

MODES = {"off": "Only the mix", "all": "A stem per track and group",
         "groups": "A stem per group"}          # "groups": tracks in no group each get their own
REQUEST = {"off": [], "all": "all", "groups": "groups"}      # what handoff.render takes


def has_groups(root: dict) -> bool:
    buses = {b["id"] for b in root.get("buses", [])}
    return any(i.get("output") in buses for i in [*root.get("tracks", []), *root.get("buses", [])]) and \
        any(routed_to_master(b) for b in root.get("buses", []))


def choices(root: dict) -> list[dict]:
    return [{"value": k, "label": v} for k, v in MODES.items() if k != "groups" or has_groups(root)]


def mode(chosen: str, root: dict) -> str:
    """The chosen stems mode, or "all" once the song has no group left to make "groups" mean something."""
    return chosen if chosen != "groups" or has_groups(root) else "all"


def listed() -> list[dict]:
    return [{"value": k, "label": v["label"], "detail": v["detail"]} for k, v in presets.PRESETS.items()]


def matching(now: dict, root: dict) -> str:
    """The preset the sheet's choices (format, sampleRate, trim, stems, markers) equal, "" when none. A preset's stems are
    read the way the sheet reads its own (`mode`): a song with no group has no "groups", so "all" is what the preset gives there."""
    def same(p: dict, f: str) -> bool:
        return now[f] == (mode(p[f], root) if f == "stems" else p[f])
    return next((k for k, p in presets.PRESETS.items() if all(same(p, f) for f in now)), "")
