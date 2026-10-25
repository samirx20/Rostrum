"""Ctrl+K's rows for the screen's own jobs. They are made from the key map (keys.KEYMAP: the same list as the shortcuts and
the Keys sheet), so a job with a key is in Ctrl+K by that fact: export, undo, redo, Preferences, snapping, fit, loop, zoom, History,
the Library, Guides, the Keys list, the playhead, markers ... The few jobs with no key (tempo, grid) are listed here.
Running one: `job:<job>` (ActionSlots.run): a ROUTE calls its bridge method, anything else is the window's to run (jobWanted)."""
from __future__ import annotations

from .keys import KEYMAP, ROUTES

SHELL_RUN = ("undo", "redo", "export", "export_again", "history", "guides", "key_list", "fold_panels", "preferences", "quit",
             "new", "open", "save_version", "duplicate_file", "add_file")       # the window runs these (Main.qml › runSoundJob)
NO_KEY = [("tempo", "Song settings: tempo, key, length", "tempo bpm key length meter time signature song"),
          ("grid", "Grid steps", "grid snap resolution steps"),
          ("add_section", "Add a section", "section part verse chorus drop new")]
ALSO = {"guides": "help how to", "key_list": "keys shortcuts", "preferences": "settings speakers audio", "export": "render bounce save wav mp3",
        "snap": "grid", "fit": "zoom", "fit_all": "zoom whole song", "history": "versions changes", "library": "sounds instruments add"}


def rows(taken: set[str]) -> list[dict]:
    """`taken`: the jobs an action of the list already shows (Ctrl+K lists those itself)."""
    out = []
    for e in KEYMAP.entries():
        job = e["job"]
        if job in taken or job == "command_box" or job.startswith("nudge_") or (job not in ROUTES and job not in SHELL_RUN):
            continue
        out.append({"key": f"job:{job}", "label": e["label"], "hint": e["area"], "keys": e["keys"][0] if e["keys"] else "",
                    "words": f'{e["label"]} {ALSO.get(job, "")}', "weight": 3})
    return out + [{"key": f"job:{j}", "label": label, "hint": "Song", "keys": "", "words": words, "weight": 3} for j, label, words in NO_KEY]
