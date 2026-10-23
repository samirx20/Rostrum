"""The window and an agent's server share one file (live.py): nobody's steps are wiped, and the person's Ctrl+Z takes
back only the person's own steps; the agent's run stays until the person takes it back whole, in one step."""
from rostrum_core import Document, Who, live, toy

SAM, AGENT = Who.person("sam"), Who.agent("claude-code")


def move(x):
    return {"op": "layer.move", "target": ["card"], "args": {"x": x}}


def test_ctrl_z_takes_back_only_your_own_steps_across_window_and_agent(tmp_path):
    toy.sample(tmp_path, "itm").save()
    window, server = (Document.open(tmp_path, "itm", toy.KIND) for _ in range(2))
    live.keep(window), live.keep(server)
    window.apply(move(40), SAM)
    server.apply({"op": "camera.set", "target": ["cam_1"], "args": {"dof": True}}, AGENT, session="claude-run-1")
    server.apply({"op": "layer.rename", "target": ["title"], "args": {"name": "Hello"}}, AGENT, session="claude-run-1")
    heard = window.live.catch_up()                                   # the window's timer
    assert [c.who for c in heard] == [AGENT, AGENT] and window.data == server.data

    window.undo(SAM)                                                 # Ctrl+Z: the person's move, not the agent's work
    assert window.item("card")["x"] == 0 and window.item("cam_1")["dof"] is True
    window.undo_session("claude-run-1", SAM)                         # History › Undo all: the whole run, one step
    assert window.item("cam_1")["dof"] is False and window.item("title")["name"] != "Hello"
    assert window.seq == 5

    server.apply(move(7), AGENT)                                     # the server took in both undos before its step
    window.live.catch_up()
    assert window.data == server.data and window.item("card")["x"] == 7 and window.item("cam_1")["dof"] is False
    assert Document.open(tmp_path, "itm", toy.KIND).seq == 6         # the file only grew: nothing wiped


def test_the_document_file_is_never_more_than_a_fold_behind_the_history(tmp_path):
    """A program reading only the document file (project list names, anything that skips the history) sees a song at most
    FOLD_STEPS steps old."""
    import json
    toy.sample(tmp_path, "itm").save()
    doc = Document.open(tmp_path, "itm", toy.KIND)
    live.keep(doc)
    for x in range(live.FOLD_STEPS):
        doc.apply(move(x + 1), AGENT)           # (a person's quick repeats merge into one step)
    on_disk = json.loads((tmp_path / "docs" / f"itm{toy.KIND.ext}").read_text(encoding="utf-8"))
    assert on_disk["at"] == doc.seq and on_disk["doc"] == doc.data
