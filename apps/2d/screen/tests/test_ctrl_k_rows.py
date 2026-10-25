"""Ctrl+K has a row for every job 2D's key map runs and for every Help entry (one source each: keys2d.KEYS2D, job_rows.HELP)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rostrum_gui import job_rows

from screen2d.actions import LIST
from screen2d.keys2d import HAVE_ROWS, KEYS2D, ROUTES, SHELL, WINDOW


def test_ctrl_k_has_a_row_for_every_job_2d_runs_and_every_help_entry():
    acted = {LIST.job_of(a) for a in LIST.actions}
    made = {r["key"] for r in job_rows.rows(KEYS2D, set(ROUTES) | set(WINDOW) | set(SHELL) | {"play"}, acted | set(HAVE_ROWS) | {"select_all"}, state={"selected": True, "problems": True})}
    runs = (set(ROUTES) | set(WINDOW) | set(SHELL) | {"play"}) - acted - set(HAVE_ROWS) - {"select_all", "command_box"}
    want = {f"job:{j}" for j in runs if not j.startswith("nudge_") and KEYS2D.has(j)} | {f"job:{j}" for j, *_ in job_rows.HELP} | {f"job:{j}" for j, *_ in job_rows.CONTEXT}
    assert want <= made, f"Ctrl+K misses: {sorted(want - made)}"
