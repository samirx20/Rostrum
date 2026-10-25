"""Ctrl+K's one ranking rule, and the Help menu / AppShell staying one list (job_rows.HELP)."""
import re
from pathlib import Path

from rostrum_gui import commands, job_rows

QML = Path(__file__).resolve().parents[1] / "qml" / "RostrumKit"


def _c(label, words="", own=False, makes=False, hint="", weight=1):
    return {"key": label, "label": label, "words": words, "hint": hint, "own": own, "makes": makes, "weight": weight}


def first(rows, q):
    found = commands.search(rows, q)
    return found[0]["label"] if found else None


def test_a_name_that_starts_with_the_word_wins_and_the_selection_s_own_action_goes_first():
    rows = [_c("Split into parts (stems)", weight=0), _c("Split at the playhead", own=True, weight=3)]
    assert first(rows, "split") == "Split at the playhead"
    assert first(rows, "split into") == "Split into parts (stems)"


def test_something_new_is_never_found_by_a_loose_word():
    rows = [_c("Add group", words="a group to mute or solo together", makes=True), _c("Mute", own=True)]
    assert first(rows, "mute") == "Mute"
    assert commands.search(rows[:1], "mute") == []                 # nothing to mute: it does not add a group instead
    assert first(rows[:1], "add gr") == "Add group"                # by its name it is found


def test_a_job_row_beats_a_scene_whose_summary_says_the_word():
    rows = [_c("Add scene", words="a scene is what you export", makes=True), _c("Export…", own=True)]
    assert first(rows, "export") == "Export…"


def test_help_menu_entries_are_ctrl_k_rows_and_the_shell_runs_them():
    bar = (QML / "TopBar.qml").read_text(encoding="utf-8")
    help_menu = bar[bar.index("id: helpMenu"):]
    values = set(re.findall(r'value: "(\w+)"', help_menu[:help_menu.index("onPicked")]))
    assert values - {"guides", "keys"} == {j for j, *_ in job_rows.HELP}, "the Help menu and job_rows.HELP differ"
    shell = (QML / "AppShell.qml").read_text(encoding="utf-8")
    assert all(f'case "{j}":' in shell for j, *_ in (*job_rows.HELP, *job_rows.CONTEXT, ("find_setting",)))
