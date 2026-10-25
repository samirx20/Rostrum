"""Ctrl+K's rows for every job of an app's key map and every Help entry, made from their one source each, so nothing a key
or a menu offers can be missing from the command bar: the key map (keymap.KeyMap: the same list the shortcuts and the Keys
sheet read), the kit's Help menu (HELP, the entries TopBar.qml's Help menu draws) and the few jobs with no key (`extra`).
The ≡ menu's rows come from the project files (file_menu.FileMenuSlots.commands). Running one: `job:<job>`; the app's
`run` calls its own route or asks the window (`jobWanted` / `windowJob`), which ends in AppShell.runJob for the kit's.
"""
from __future__ import annotations

# the Help menu's entries that are no key's job: (job, label, words); the Help menu in TopBar.qml draws the same three
HELP = (("agents", "Connect an AI agent…", "agent claude codex mcp connect"),
        ("report", "Report a problem…", "bug feedback issue"),
        ("about", "About and licences", "version credits notices licence license"))
# jobs that exist only while something is true (no row otherwise: "only what can run now"): (job, label, words, state)
CONTEXT = (("problems", "Problems", "warning issue error list top bar chip", "problems"),)
# what else a key map job answers to
ALSO = {"guides": "help how to", "key_list": "keys shortcuts", "preferences": "settings speakers audio",
        "export": "render bounce save wav mp3", "snap": "grid", "fit": "zoom", "fit_all": "zoom whole", "history": "versions changes",
        "library": "sounds instruments add", "play": "stop pause start", "fold_panels": "hide show side panels",
        "next_area": "focus move between", "undo": "back step", "redo": "forward again",
        **{f"nudge_{d}{s}": "move arrow" for d in ("left", "right", "up", "down") for s in ("", "_big", "_fine")}}


def rows(keymap, runnable, taken=(), extra=(), hint="", state=None) -> list[dict]:
    """`runnable`: the jobs this app runs; `taken`: the jobs a row of the app's action list or the ≡ menu already shows;
    `extra`: (job, label, hint, words) for a job with no key.
    `state`: {"selected": bool, "problems": bool}: Find a setting is a row only while something is selected, Problems only while
    the chip shows. Every other key of the Keys sheet is a row (the nudges too: "nudge" finds them), so Ctrl+K and the
    sheet are one list."""
    state = state or {}
    out = []
    for e in keymap.entries():
        job = e["job"]
        if job in taken or job == "command_box" or job not in runnable or (job == "find_setting" and not state.get("selected")):
            continue
        out.append({"key": f"job:{job}", "label": e["label"], "hint": e["area"], "keys": e["keys"][0] if e["keys"] else "",
                    "words": f'{e["label"]} {ALSO.get(job, "")}', "weight": 3, "own": True})
    out += [{"key": f"job:{j}", "label": label, "hint": h or hint, "keys": "", "words": words, "weight": 3, "own": True}
            for j, label, h, words in extra]
    out += [{"key": f"job:{j}", "label": label, "hint": "Top bar", "keys": "", "words": words, "weight": 3, "own": True}
            for j, label, words, when in CONTEXT if state.get(when)]
    return out + [{"key": f"job:{j}", "label": label, "hint": "Help", "keys": "", "words": words, "weight": 3} for j, label, words in HELP]
