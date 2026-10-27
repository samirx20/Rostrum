"""Try before you keep (INTERACTION.md 1.21 rule 6): a choice only hovered in an amounts box shows on the work and goes
back when its list closes; a pick stays; Esc leaves no step; Enter keeps exactly one, with what was set (never a
choice that was only hovered)."""
from types import SimpleNamespace

from PySide6.QtCore import QCoreApplication
from rostrum_core import Param

from rostrum_gui.actions import Action
from rostrum_gui.amounts_page import AmountsPage

EASE = Param("ease", "choice", label="Ease", options=["linear", "in", "out"], default="linear")


class Drag:
    """A document drag: what it shows now (`shown`), and how it ended."""
    def __init__(self):
        self.shown, self.ended = None, None

    def fresh_calls(self, fn):
        return fn()

    def same(self, calls):
        return False

    def preview(self, calls, fresh=False):
        self.shown = calls[0]["args"]["ease"]

    def end(self, cancel=False, label=None):
        self.ended = "cancel" if cancel else label
        return None if cancel else SimpleNamespace(label=label)


def _page():
    _app = QCoreApplication.instance() or QCoreApplication([])
    drags = []
    page = AmountsPage(lambda label: drags.append(Drag()) or drags[-1], lambda change, label: None, lambda line: None)
    action = Action("ease", "Ease", amounts=("ease",), calls=lambda f, am: [{"op": "key.ease", "target": ["k1"],
                                                                         "args": {"ease": am.get("ease", "linear")}}])
    registry = SimpleNamespace(get=lambda op: SimpleNamespace(params=[EASE]))
    facts = SimpleNamespace(ids=["k1"], items=[{"id": "k1", "type": "key"}],
                            doc=SimpleNamespace(kind=SimpleNamespace(registry=registry)))
    page.open(action, facts, "Ease")
    return page, drags


def _settle(page):
    page._later.flush()


def test_hovered_choice_shows_then_goes_back_and_a_pick_stays():
    page, drags = _page()
    page.tryValue("ease", "in")
    _settle(page)
    assert drags[0].shown == "in"                 # resting on "in" shows it on the work
    page.untry()                                  # the list closed with no pick
    _settle(page)
    assert drags[0].shown == "linear"
    page.tryValue("ease", "out")
    page.setValue("ease", "out")                  # picked: the list then closes (untried) and the pick stays
    page.untry()
    _settle(page)
    assert drags[0].shown == "out"
    page.keep()
    assert drags[0].ended and "Ease" in drags[0].ended


def test_esc_records_nothing_and_enter_keeps_what_was_set_not_hovered():
    page, drags = _page()
    page.tryValue("ease", "in")
    page.cancel()
    assert drags[0].ended == "cancel"
    page, drags = _page()
    page.tryValue("ease", "out")                  # only hovered when Enter lands: not kept
    page.keep()
    assert drags[0].shown == "linear" and drags[0].ended not in (None, "cancel")
