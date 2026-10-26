"""A window's change writes its history line the frame after (live.Live.flush, pending.py): a crash before that line
still brings the step back on open, and Ctrl+Z right after works and is kept."""
import subprocess
import sys
import textwrap
from pathlib import Path

from rostrum_core import Document, Who, live, toy

SAM = Who.person("sam")
ROOT = Path(__file__).resolve().parents[3]


def move(x):
    return {"op": "layer.move", "target": ["card"], "args": {"x": x}}


def _window(folder, owed):
    doc = Document.open(folder, "itm", toy.KIND)
    live.keep(doc).windowed(lambda: owed.append(doc.live))
    return doc


def _killed_after(folder, steps):
    """A window process makes `steps` (python lines, `doc` the document), then is killed by its PID before any line
    owed is written (its frame-after never comes)."""
    code = textwrap.dedent(f"""
        import sys; sys.path.insert(0, {str(ROOT / 'shared' / 'core')!r})
        from rostrum_core import Document, Who, live, toy
        SAM = Who.person("sam")
        doc = Document.open({str(folder)!r}, "itm", toy.KIND)
        live.keep(doc).windowed(lambda: None)
        def move(x): return {{"op": "layer.move", "target": ["card"], "args": {{"x": x}}}}
    """) + "\n".join(steps) + "\nprint('done', flush=True)\nimport time; time.sleep(60)\n"
    p = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
    try:
        assert p.stdout.readline().strip() == "done"
    finally:
        p.kill()                                    # TerminateProcess: no clean-up, no flush
        p.wait(10)


def test_a_crash_right_after_a_key_still_has_the_step(tmp_path):
    toy.sample(tmp_path, "itm").save()
    _killed_after(tmp_path, ["doc.apply(move(40), SAM, join=False)"])
    doc = Document.open(tmp_path, "itm", toy.KIND)
    assert doc.item("card")["x"] == 40 and doc.seq == 1
    assert any("brought back" in n for n in doc.notes)
    live.keep(doc)                                  # the step is written now: the next open finds it in the file
    again = Document.open(tmp_path, "itm", toy.KIND)
    assert again.item("card")["x"] == 40 and again.seq == 1 and not again.notes


def test_a_crash_right_after_an_undo_still_has_the_undo(tmp_path):
    toy.sample(tmp_path, "itm").save()
    _killed_after(tmp_path, ["doc.apply(move(40), SAM, join=False)", "doc.apply(move(70), SAM, join=False)",
                             "doc.undo(SAM)"])
    doc = Document.open(tmp_path, "itm", toy.KIND)
    assert doc.item("card")["x"] == 40 and doc.seq == 3 and doc.history.changes[-1].undoes == [2]
    doc.redo(SAM)                                   # the undo is a real one: redo brings 70 back
    assert doc.item("card")["x"] == 70


def test_undo_right_after_a_change_works_and_both_are_kept(tmp_path):
    toy.sample(tmp_path, "itm").save()
    owed = []
    doc = _window(tmp_path, owed)
    doc.apply(move(40), SAM, join=False)
    meanwhile = Document.open(tmp_path, "itm", toy.KIND)                  # an agent opening it before that frame:
    assert owed and meanwhile.seq == 0 and not meanwhile.notes            # the line is coming, nothing made twice
    doc.undo(SAM)                                                         # before that frame: the line goes first
    assert doc.item("card")["x"] == 0
    doc.live.flush()
    reopened = Document.open(tmp_path, "itm", toy.KIND)
    assert reopened.seq == 2 and reopened.item("card")["x"] == 0 and not reopened.notes


def test_a_crash_right_after_a_live_box_is_kept_still_has_it(tmp_path):
    """Stagger…'s and the amounts popover's box (a fresh gesture): Enter keeps it, and a crash before its line keeps
    it too."""
    toy.sample(tmp_path, "itm").save()
    _killed_after(tmp_path, ["with doc.gesture('Move', SAM) as g:",
                             "    g.preview([move(10)], fresh=True)",
                             "    g.preview([move(55)], fresh=True)"])
    doc = Document.open(tmp_path, "itm", toy.KIND)
    assert doc.item("card")["x"] == 55 and doc.seq == 1
