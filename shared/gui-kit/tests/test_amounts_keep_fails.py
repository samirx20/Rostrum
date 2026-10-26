"""A kept amounts session that the document refuses at the end (the notes it read changed meanwhile) says so in plain
words, records nothing and leaves no gesture open; no code id reaches the person (critic r9)."""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rostrum_core import RostrumError  # noqa: E402
from rostrum_gui.amounts_page import AmountsPage  # noqa: E402


class RefusingDrag:
    ended = 0

    def end(self, cancel=False, calls=None, label=None):
        RefusingDrag.ended += 1                      # (a real Drag closes its gesture before the commit can fail)
        raise RostrumError.not_found("apply", "note", "track_1.n8000", ["track_1.n6000"])


def test_refused_keep_is_said_plainly_and_closes():
    said, kept = [], []
    page = AmountsPage(lambda label: None, lambda c, label: kept.append(c), said.append)
    page._drag, page._action, page._title, page._rows = RefusingDrag(), SimpleNamespace(id="repeat"), "Repeat", []
    page.keep()
    assert page._drag is None and not kept and RefusingDrag.ended == 1
    assert said and said[0].startswith("Repeat was not added.") and "n8000" not in said[0] and "track_1" not in said[0]
