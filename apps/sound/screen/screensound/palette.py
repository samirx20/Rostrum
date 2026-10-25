"""Ctrl+K's rows for Sound's own jobs: the shared job rows (rostrum_gui/job_rows.py: every key map job Sound runs, the Help
menu's entries) and the few jobs with no key. A job with a key is in Ctrl+K by that fact (keys.KEYMAP is the one list
the shortcuts, the Keys sheet and this read); the ≡ menu's rows come from the project files (ProjectFiles.commands).
Running one: `job:<job>` (ActionSlots.run): a ROUTE calls its bridge method, anything else is the window's to run (jobWanted)."""
from __future__ import annotations

from rostrum_gui import job_rows

from . import lanes
from .keys import FILE_JOBS, KEYMAP, ROUTES, SHELL_RUN

NO_KEY = [("tempo", "Song settings: tempo, key, length", "Song", "tempo bpm key length meter time signature song"),
          ("grid", "Grid steps", "Song", "grid snap resolution steps"),
          ("add_section", "Add a section", "Song", "section part verse chorus drop new"),
          ("loudness", "Loudness", "Top bar", "lufs level target mixer meter"),           # the loudness chip's click: the Mixer
          ("sample_rate", "Sample rate", "Settings", "khz hz quality 44.1 48 preferences")]   # Preferences, where it is set


def rows(taken: set[str], state: dict | None = None) -> list[dict]:
    """`taken`: the jobs an action of the list already shows (Ctrl+K lists those itself)."""
    return job_rows.rows(KEYMAP, set(ROUTES) | set(SHELL_RUN), taken | set(FILE_JOBS), NO_KEY, state=state)


def lane_rows(doc, track_id: str, open_lane, open_play_lane) -> list[dict]:
    """The selected track's lanes, as its A button and lane picker offer them: "Show the Volume lane" (automation under
    its row: lanes.applicable, the track's own) and, for a track that plays notes, the Editor's playing lane (Sustain,
    Expression, Bend). `open_lane(track, target, lane)` / `open_play_lane(lane)` are the bridge's (lane_slots.py)."""
    if not track_id:
        return []
    track = doc.item(track_id)
    name = track.get("name") or track_id
    out = [{"key": f"lane:{lane}", "label": f"Show the {lanes.label(lane)} lane", "hint": name, "weight": 3,
            "words": f"automation lane curve points {lanes.label(lane)} {lane}",
            "do": lambda ln=lane: open_lane(track_id, track_id, ln)}
           for target, lane in lanes.applicable(track, doc.data) if target == track_id]
    if any(lane in lanes.MELODIC_ONLY for _, lane in lanes.applicable(track, doc.data)):
        out += [{"key": f"playlane:{lane}", "label": f"Playing lane: {lanes.label(lane)}", "hint": name, "weight": 3,
                 "words": f"editor lane pedal wheel controller {lanes.label(lane)} {lane}",
                 "do": lambda ln=lane: open_play_lane(ln)} for lane in lanes.PLAYED]
    return out
