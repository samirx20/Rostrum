"""When a clip's Cleanup settings are on screen (rule of individuality: absent, never greyed; no Qt).

Clean-up is for speech and recordings. A clip shows its Cleanup rows once it is a take recorded here, already has a
step set (`cleanup.needs_cleanup`), or the person asked for it ("Clean up…", `Asked`). Every other clip (a tone, a
sound effect) leaves them out. This is only what the screen shows: the operations take these fields on any clip, so
an agent can clean any file.
"""
from __future__ import annotations

from pathlib import Path

from rostrum_sound import cleanup

FIELDS = ("stem", "isolate", "denoise", "dereverb", "useCleaned")


def recorded_here(item: dict) -> bool:
    """A take made by Record (`media/<track>-take-<n>.wav`, rostrum_sound.record): a voice or an instrument close to a microphone."""
    return "-take-" in Path(str(item.get("media", ""))).name


class Asked:
    """The clips whose Cleanup rows the person asked for (screen state, never saved in the song)."""
    def __init__(self):
        self.ids: set[str] = set()

    def left_out(self, item: dict) -> set[str]:
        """The Cleanup fields to leave out of this item's panel."""
        if item.get("type") != "clip" or item.get("id") in self.ids or recorded_here(item) or cleanup.needs_cleanup(item):
            return set()
        return set(FIELDS)
