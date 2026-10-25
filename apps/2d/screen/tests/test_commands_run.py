"""Every Ctrl+K entry the screen offers does something visible when run (a change, a pick, a status line, or a request the
window answers, an Edit <setting> its row shown): none is offered that would do nothing (the base: commands.runs,
job_when.WHEN, command_words: only a setting the panel shows)."""
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QObject
from PySide6.QtTest import QSignalSpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document  # noqa: E402
from rostrum2d import KIND, run_source, textsize  # noqa: E402
from screen2d import frames  # noqa: E402
from screen2d.bridge2d import Bridge2D  # noqa: E402
from screen2d.sample import SOURCE  # noqa: E402
from test_screen import FakeEngine  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

# the OS file windows, quitting and the whole-file swaps: they open a window of their own, not tried here
SKIP = {"job:quit", "job:export", "job:export_again", "file:new", "file:open", "add:file", "file:start", "file:duplicate",
        "file:folder", "job:agents", "job:report", "job:about", "job:history", "job:guides", "job:key_list"}
PICKS = {"nothing": "", "a shape": "rule", "the text": "title", "the Frame": "frame"}


@pytest.fixture
def bridge(monkeypatch):
    QGuiApplication.instance() or QGuiApplication([])
    monkeypatch.setattr(frames, "open_engine", FakeEngine)
    monkeypatch.setattr(textsize, "open_engine", FakeEngine)
    monkeypatch.setattr(textsize, "_own", None)
    doc = Document.new(KIND)
    doc.run_script("a.py", run_source(SOURCE, "a.py"))
    b = Bridge2D(doc)
    yield b
    b.close()


def _signals(b):
    objs = [b, b._hub, b._adder] + [getattr(b, n) for n in ("_stagger", "_depth_typed", "_cuepick", "_lipsync", "_blinks") if hasattr(b, n)]
    return [QSignalSpy(getattr(o, m.name().data().decode())) for o in objs for m in
            (o.metaObject().method(i) for i in range(o.metaObject().methodCount()))
            if m.methodType().name == "Signal" and m.name().data().decode() in (
                "viewRequested", "renameRequested", "windowJob", "findAsked", "fileWanted", "opened", "fieldRevealed")]


def _trace(b):
    return (len(b.doc.history.changes), tuple(b.selected_layers()), b.status, b.time, b.tool, b.play.playing, tuple(b._keys.ids), tuple(b._kit.selection), frozenset(b._anim_only))


@pytest.mark.parametrize("pick", PICKS)
def test_every_ctrl_k_entry_does_something_visible(bridge, pick):
    b = bridge
    b.setTime(1.0)
    keys = []
    b.select(PICKS[pick]) if PICKS[pick] else None
    keys = [c["key"] for c in b.commands("") if c["key"] not in SKIP]
    assert keys, "Ctrl+K offers nothing"
    dead, spies, offered = [], _signals(b), {c["key"] for c in b.commands("")}
    for key in keys:
        b.play.stop(); b.setTime(1.0); b.select(PICKS[pick])
        if key not in offered:
            continue                                     # an earlier entry changed what is offered (it was undone after)
        before = _trace(b)
        counts = [s.count() for s in spies]
        ok = b.run(key)
        fired = any(s.count() != n for s, n in zip(spies, counts))
        if ok is not True or not (fired or _trace(b) != before):
            dead.append((key, ok, b.status[:80]))
        b.play.stop()
        n = len(b.doc.history.changes) - before[0]
        for _ in range(max(0, n)):
            b.undo()
        if n:
            offered = {c["key"] for c in b.commands("")}
    assert not dead, f"offered in Ctrl+K but did nothing visible ({pick}): {dead}"

