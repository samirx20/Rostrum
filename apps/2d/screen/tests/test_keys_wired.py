"""Every key on the Keys sheet (Ctrl+/) does something: the sheet and the shortcuts are one list (keys2d.KEYS2D)."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from screen2d.actions import LIST
from screen2d.bridge2d import Bridge2D
from screen2d.keys2d import KEYS2D, ROUTES, SKIP, WINDOW

QML = Path(__file__).resolve().parents[1] / "qml" / "Main.qml"


def test_every_listed_key_has_something_behind_it():
    behind = set(ROUTES) | set(WINDOW) | set(SKIP) | {LIST.job_of(a) for a in LIST.actions}
    dead = [(e["job"], e["keys"]) for e in KEYS2D.entries() if e["job"] not in behind]
    assert not dead, f"listed on the Keys sheet but nothing runs: {dead}"


def test_routes_name_real_bridge_methods_and_window_jobs_are_answered():
    missing = [(j, r[0]) for j, r in ROUTES.items() if not hasattr(Bridge2D, r[0])]
    assert not missing, f"keys2d.ROUTES names a bridge method that does not exist: {missing}"
    text = QML.read_text(encoding="utf-8")
    block = text[text.index("windowJobs: ({"):text.index("Connections { target: backend.actions; function onWindowJob")]
    unanswered = [j for j in WINDOW if not re.search(rf"\b{j}\s*:", block)]
    assert not unanswered, f"keys2d.WINDOW jobs Main.qml windowJobs does not answer: {unanswered}"


def test_a_job_has_one_owner():
    owners = [set(ROUTES), set(WINDOW), set(SKIP)]   # (a ROUTE or WINDOW job may take over an action's key: Delete runs strokes and keys first)
    both = {j for i, a in enumerate(owners) for b in owners[i + 1:] for j in a & b}
    assert not both, f"two owners for one key job (the key would fire twice or not at all): {both}"
