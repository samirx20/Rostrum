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


def test_a_window_writes_the_whole_file_only_when_quiet_and_never_loses_a_step(tmp_path, monkeypatch):
    """A window (LiveLink) never writes the whole document inside a change: its timer folds once the person pauses.
    Before that, a crash-like reopen (nothing folded) and another program sharing the file still see every step."""
    import json
    toy.sample(tmp_path, "itm").save()
    window, server = (Document.open(tmp_path, "itm", toy.KIND) for _ in range(2))
    live.keep(window).windowed(), live.keep(server)
    file = tmp_path / "docs" / f"itm{toy.KIND.ext}"
    at = json.loads(file.read_text(encoding="utf-8"))["at"]
    for x in range(live.FOLD_STEPS + 3):
        window.apply(move(x + 1), SAM, join=False)
        if x == 5:
            server.apply({"op": "layer.rename", "target": ["title"], "args": {"name": "Hi"}}, AGENT)
    assert json.loads(file.read_text(encoding="utf-8"))["at"] == at          # nothing whole written in a change
    assert window.live.fold_if_quiet() is True                              # 20 steps behind: folds even mid-work
    window.undo(SAM)
    assert window.live.fold_if_quiet() is False                             # just changed: waits for a pause
    crashed = Document.open(tmp_path, "itm", toy.KIND)                       # the window died before folding
    assert crashed.seq == window.seq and crashed.data == window.data and crashed.item("title")["name"] == "Hi"
    monkeypatch.setattr(live, "FOLD_QUIET_S", 0.0)
    assert window.live.fold_if_quiet() is True and window.live.fold_if_quiet() is False
    on_disk = json.loads(file.read_text(encoding="utf-8"))
    assert on_disk["at"] == window.seq and on_disk["doc"] == window.data
    server.apply(move(99), AGENT)                                            # the agent's server took in every step
    assert Document.open(tmp_path, "itm", toy.KIND).seq == window.seq + 1 == server.seq
