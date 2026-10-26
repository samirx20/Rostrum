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
    window.live.settle()                                                     # (the link makes it between events)
    window.undo(SAM)
    assert window.live.fold_if_quiet() is False                             # just changed: waits for a pause
    crashed = Document.open(tmp_path, "itm", toy.KIND)                       # the window died before folding
    assert crashed.seq == window.seq and crashed.data == window.data and crashed.item("title")["name"] == "Hi"
    monkeypatch.setattr(live, "FOLD_QUIET_S", 0.0)
    assert window.live.fold_if_quiet() is True and window.live.fold_if_quiet() is False
    window.live.settle()                                                     # (written on its own thread)
    on_disk = json.loads(file.read_text(encoding="utf-8"))
    assert on_disk["at"] == window.seq and on_disk["doc"] == window.data
    server.apply(move(99), AGENT)                                            # the agent's server took in every step
    assert Document.open(tmp_path, "itm", toy.KIND).seq == window.seq + 1 == server.seq


def _held_write(monkeypatch, fail=False):
    """The window's document-file write, held on its thread until the test lets it go (a slow or failing disk)."""
    import threading
    go = threading.Event()
    from rostrum_core import doc_write
    real = doc_write.write_document

    def slow(*a, **kw):
        assert go.wait(10), "the write was never let go"
        if fail:
            raise OSError("disk full")
        return real(*a, **kw)
    monkeypatch.setattr(doc_write, "write_document", slow)
    monkeypatch.setattr(live, "FOLD_QUIET_S", 0.0)
    return go


def test_a_key_never_waits_for_the_document_file_being_written(tmp_path, monkeypatch):
    """The quiet fold writes on its own thread: while it is held (a slow disk), changes and timer ticks go on at
    once, and Save still ends with the newest song in the file."""
    import json
    import time
    toy.sample(tmp_path, "itm").save()
    window = Document.open(tmp_path, "itm", toy.KIND)
    live.keep(window).windowed()
    window.apply(move(1), SAM, join=False)
    go = _held_write(monkeypatch)
    assert window.live.fold_if_quiet() is True                     # the write starts (its text made between events),
    while window.live.fold_work():                                 # and the file write is held
        pass
    t = time.perf_counter()
    window.apply(move(2), SAM, join=False)                         # a key while the file is being written
    assert window.live.fold_if_quiet() is False                    # the next tick doesn't wait either
    assert time.perf_counter() - t < 1.0
    go.set()
    window.save()                                                  # Save (and close) wait, then write what is newer
    on_disk = json.loads((tmp_path / "docs" / f"itm{toy.KIND.ext}").read_text(encoding="utf-8"))
    assert on_disk["at"] == window.seq and on_disk["doc"] == window.data


def test_a_failed_document_write_is_said_and_tried_again(tmp_path, monkeypatch):
    import pytest
    from rostrum_core import RostrumError
    toy.sample(tmp_path, "itm").save()
    window = Document.open(tmp_path, "itm", toy.KIND)
    live.keep(window).windowed()
    window.apply(move(1), SAM, join=False)
    go = _held_write(monkeypatch, fail=True)
    assert window.live.fold_if_quiet() is True
    while window.live.fold_work():
        pass
    go.set()
    with pytest.raises(RostrumError) as e:                         # the link's next tick: loud, in the top bar
        window.live.settle()
    assert "disk full" in str(e.value) and "Nothing is lost" in e.value.person()
    assert window.live.behind()                                    # never taken for written
    monkeypatch.undo()
    monkeypatch.setattr(live, "FOLD_QUIET_S", 0.0)
    assert window.live.fold_if_quiet() is True                     # tried again
    window.live.settle()
    assert not window.live.behind()


def test_a_window_reads_an_unchanged_history_file_once_whatever_its_layout(tmp_path, monkeypatch):
    """The window's timer reads nothing while the history file is as it left it: after its own steps, and after
    opening a file saved before S39 (layout 1: once re-read in whole on every tick until the person changed something).
    Another program's step is still taken in, and the next save writes the new layout."""
    import json
    doc = toy.sample(tmp_path, "itm")
    doc.apply(move(5), SAM)
    kind, hist = toy.KIND, tmp_path / ".rostrum" / "itm.history.jsonl"
    lines = [json.dumps({"format": kind.format, "version": kind.version, "base": doc.base})]
    hist.parent.mkdir()
    hist.write_text("\n".join(lines + [json.dumps(c.to_dict()) for c in doc.history.changes]) + "\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / f"itm{kind.ext}").write_text(json.dumps(
        {"format": kind.format, "version": kind.version, "saved_by": "0.1.2", "doc": doc.data}), encoding="utf-8")
    reads, read = [], live.read_history
    monkeypatch.setattr(live, "read_history", lambda *a, **k: reads.append(a[2:3]) or read(*a, **k))
    window = Document.open(tmp_path, "itm", kind)
    live.keep(window).windowed()
    for _ in range(3):
        window.live.catch_up()
    assert reads == []
    server = Document.open(tmp_path, "itm", kind)
    live.keep(server)
    server.apply(move(9), AGENT)                                     # rewrites the old file whole, new layout
    assert [c.who for c in window.live.catch_up()] == [AGENT] and window.data == server.data
    window.apply({"op": "layer.rename", "target": ["title"], "args": {"name": "Hi"}}, SAM)
    reads.clear()
    window.live.catch_up(), server.live.catch_up(), window.live.catch_up()
    assert len(reads) == 1 and reads[0] != (0,) and server.data == window.data   # the server read only the new line
    assert '"layout":2' in hist.read_text(encoding="utf-8").split("\n")[0]
