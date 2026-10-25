"""Ctrl+K's rows for Sound's own jobs: the shared job rows (rostrum_gui/job_rows.py: every key map job Sound runs, the Help
menu's entries) and the few jobs with no key. A job with a key is in Ctrl+K by that fact (keys.KEYMAP is the one list
the shortcuts, the Keys sheet and this read); the ≡ menu's rows come from the project files (ProjectFiles.commands).
Running one: `job:<job>` (ActionSlots.run): a ROUTE calls its bridge method, anything else is the window's to run (jobWanted)."""
from __future__ import annotations

from rostrum_gui import job_rows

from .keys import FILE_JOBS, KEYMAP, ROUTES, SHELL_RUN

NO_KEY = [("tempo", "Song settings: tempo, key, length", "Song", "tempo bpm key length meter time signature song"),
          ("grid", "Grid steps", "Song", "grid snap resolution steps"),
          ("add_section", "Add a section", "Song", "section part verse chorus drop new"),
          ("loudness", "Loudness", "Top bar", "lufs level target mixer meter"),           # the loudness chip's click: the Mixer
          ("sample_rate", "Sample rate", "Settings", "khz hz quality 44.1 48 preferences")]   # Preferences, where it is set


def rows(taken: set[str], state: dict | None = None) -> list[dict]:
    """`taken`: the jobs an action of the list already shows (Ctrl+K lists those itself)."""
    return job_rows.rows(KEYMAP, set(ROUTES) | set(SHELL_RUN), taken | set(FILE_JOBS), NO_KEY, state=state)
