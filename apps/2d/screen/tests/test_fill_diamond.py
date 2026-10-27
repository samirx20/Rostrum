"""The Fill row's key mark keys the fill and, on a key at the playhead, deletes it (hand maker row 15: it threw
"module 'screen2d.route' has no attribute 'key_at'" and keyed nothing)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_the_fill_diamond_keys_then_deletes_its_key():
    from rostrum_core import Document, Who
    from rostrum2d import KIND, run_source
    from screen2d import fill_rows
    d = Document.new(KIND)
    d.run_script("a.py", run_source('comp("c", duration=2, fps=25)\nshape("s", w=100, h=40, fill="#888888")\n', "a.py"))
    calls, label = fill_rows.animate_calls(d.item("s"), 0.0, 25)
    assert calls and label.startswith("Animate")
    d.apply(calls, Who.person("sam"))
    calls, label = fill_rows.animate_calls(d.item("s"), 0.0, 25)
    assert calls[0]["op"] == "key.remove" and label.startswith("Delete")
