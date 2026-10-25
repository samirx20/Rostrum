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
