"""A change of the document costs the screen no disk: after a field edit and an Undo, nothing asked the file system
(stat, listing a folder, opening a file, resolving a path). Values read from files are kept and looked at again only on
the screen's own poll (marker watch, soundtrack tick) or when this process wrote the file. A 5-20 ms stall per edit
came from such lookups repeated per layer; this guards the whole class."""
import builtins
import os
import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QGuiApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document, Who, markers, project  # noqa: E402
from rostrum2d import KIND, textsize  # noqa: E402
from screen2d import frames  # noqa: E402
from screen2d.bridge2d import Bridge2D  # noqa: E402
from test_screen import FakeEngine  # noqa: E402

PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478"
                    "9c6360000002000001e221bc330000000049454e44ae426082")


@pytest.fixture
def bridge(monkeypatch, tmp_path):
    QGuiApplication.instance() or QGuiApplication([])
    monkeypatch.setattr(frames, "open_engine", FakeEngine)
    monkeypatch.setattr(textsize, "open_engine", FakeEngine)
    monkeypatch.setattr(textsize, "_own", None)
    (tmp_path / "docs").mkdir()
    markers.edit(tmp_path, [{"op": "marker.add", "args": {"name": "reveal", "at": 1.0}}], Who.person("sam"))
    (tmp_path / "pic.png").write_bytes(PNG)
    src = project.add_file(tmp_path, "image", "pic", tmp_path / "pic.png")["file"]
    doc = Document.new(KIND, folder=tmp_path)
    calls = [{"op": "comp.add", "args": {"id": "film", "fps": 10, "duration": 5}},
             {"op": "layer.add", "target": "film", "args": {"type": "image", "id": "pic"}},
             {"op": "image.set", "target": ["pic"], "args": {"src": src, "w": 1, "h": 1}}]
    for i in range(6):
        calls += [{"op": "layer.add", "target": "film", "args": {"type": "shape", "id": f"s{i}"}},
                  {"op": "shape.set", "target": f"s{i}", "args": {"marker": "reveal"}},
                  {"op": "key.add", "target": f"s{i}", "args": {"prop": "opacity", "t": 0.0, "v": 0}},
                  {"op": "key.add", "target": f"s{i}", "args": {"prop": "opacity", "t": 1.0, "v": 1}}]
    doc.apply(calls, Who.person("sam"))
    b = Bridge2D(doc)
    yield b
    b.close()


def test_a_change_and_undo_ask_the_disk_nothing(bridge, monkeypatch):
    asked = []

    def where():
        """The three nearest callers outside this file (file:line function), read without touching any file."""
        f, out = sys._getframe(2), []
        while f and len(out) < 4:
            out.append(f"{Path(f.f_code.co_filename).name}:{f.f_lineno} {f.f_code.co_name}")
            f = f.f_back
        return " < ".join(out)

    def spy(owner, name):
        real, busy = getattr(owner, name), []

        def call(*a, **k):
            if not busy:
                busy.append(1)
                asked.append((name, str(a[0]) if a else "", where()))
                busy.clear()
            return real(*a, **k)
        monkeypatch.setattr(owner, name, call)

    for owner, name in [(os, "stat"), (os, "lstat"), (os, "scandir"), (os, "listdir"), (builtins, "open")] + \
            [(sys.modules["nt"], "_getfinalpathname")] * (os.name == "nt"):
        spy(owner, name)
    bridge.select("s0")
    bridge.setTime(1.5)
    bridge.setValue("opacity", 0.25)                    # (the first change of a session reads each file once)
    bridge.undo()
    del asked[:]
    ok = [bridge.setValue("opacity", 0.5), bridge.undo()]
    monkeypatch.undo()                                  # (the report below reads files itself)
    assert ok[0]
    # (an Undo takes in what other programs saved first: live.catch_up's one look at each open history is on purpose)
    asked = [x for x in asked if "catch_up" not in x[2]]
    assert not asked, chr(10).join(" ".join(x) for x in asked)
