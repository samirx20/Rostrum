"""History's promise: an agent's run is one row the person can take back in one step, and it then shows as taken back."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication
from rostrum_core import Who, toy

from rostrum_gui import DocBridge
from rostrum_gui.history_rows import rows

CLAUDE = Who.agent("claude-code")


def move(doc, id_, x, who, session=None):
    doc.apply([{"op": "layer.move", "target": [id_], "args": {"x": x}}], who, session=session)


def test_agent_run_folds_into_one_row_and_undo_all_marks_it_taken_back():
    _app = QCoreApplication.instance() or QCoreApplication([])
    bridge = DocBridge(toy.sample())
    doc, me = bridge.doc, bridge.who
    move(doc, "card", 10, me)
    for x in (20, 30, 40):
        move(doc, "title", x, CLAUDE, session="run-1")
    got = rows([doc], me)
    assert [r["kind"] for r in got] == ["run", "step"]
    run = got[0]
    assert run["who"] == "Claude" and run["count"] == 3 and not run["undone"]
    assert [s["seq"] for s in run["steps"]] == [4, 3, 2]          # newest first
    assert bridge.agent.chip["text"] == "Claude is working · 3 changes"

    assert bridge.undoRun("run-1")
    assert len(doc.history.changes) == 5                          # Undo all is ONE new step
    run = rows([doc], me)[0]
    assert run["kind"] == "run" and run["undone"]
    assert doc.item("title")["x"] == toy.sample().item("title")["x"]
    assert bridge.undoLabel == "Move"                             # ↶ still takes back only the person's own step
    assert [r["kind"] for r in rows([doc], me, "you")] == ["step"]
