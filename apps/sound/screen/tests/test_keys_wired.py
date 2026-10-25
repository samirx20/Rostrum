"""Every key on the Keys sheet (Ctrl+/) does something: the sheet and the shortcuts are one list (keys.KEYMAP)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from screensound.actions import LIST
from screensound.keys import KEYMAP, ROUTES, SHELL, SKIP


def test_every_listed_key_has_something_behind_it():
    behind = set(ROUTES) | set(SKIP) | set(SHELL) | {LIST.job_of(a) for a in LIST.actions}
    dead = [(e["job"], e["keys"]) for e in KEYMAP.entries() if e["job"] not in behind]
    assert not dead, f"listed on the Keys sheet but nothing runs: {dead}"


def test_ctrl_k_has_a_row_for_every_job_sound_runs_and_every_help_entry():
    from rostrum_gui.job_rows import CONTEXT, HELP

    from screensound.keys import FILE_JOBS, SHELL_RUN
    from screensound.palette import NO_KEY, rows

    made = {r["key"] for r in rows({LIST.job_of(a) for a in LIST.actions}, {"selected": True, "problems": True})}
    runs = (set(ROUTES) | set(SHELL_RUN)) - set(FILE_JOBS) - {LIST.job_of(a) for a in LIST.actions}
    want = {f"job:{j}" for j in runs if j != "command_box" and not j.startswith("nudge_") and KEYMAP.has(j)}
    want |= {f"job:{j}" for j, *_ in NO_KEY} | {f"job:{j}" for j, *_ in HELP} | {f"job:{j}" for j, *_ in CONTEXT}
    want |= {f"job:{j}" for j in ("loudness", "sample_rate")}   # the loudness chip and Preferences
    assert want <= made, f"Ctrl+K misses: {sorted(want - made)}"
