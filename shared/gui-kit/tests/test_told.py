"""No action is silent (INTERACTION.md 1.21 rule 9): an action that changed the document and said nothing gets its own
words in the message line; an app's own words are never overwritten; a person's undo flashes what it took back."""
from types import SimpleNamespace

from PySide6.QtCore import Property, QObject, Signal

from rostrum_gui.action_hub import ActionHub
from rostrum_gui.actions import Action, ActionList
from rostrum_gui.keymap import KeyMap


class Host(QObject):
    """The kit DocBridge's two signals and its message line, nothing else."""
    statusChanged = Signal()
    docChanged = Signal()

    def __init__(self):
        super().__init__()
        self._status = ""

    def set_status(self, text):
        self._status = text
        self.statusChanged.emit()

    status = Property(str, lambda self: self._status, notify=statusChanged)


def _hub(host, actions, apply_fn):
    facts = SimpleNamespace(ids=["a", "b", "c"], items=[{"id": i, "type": "shape"} for i in "abc"])
    return ActionHub(ActionList(actions, KeyMap("test")), lambda: facts, lambda f: f"{len(f.ids)} layers", apply_fn,
                     None, host.set_status, parent=host)


def _calls(f):
    return [{"op": "x.y", "target": list(f.ids), "args": {}}]


def test_a_silent_action_says_what_it_did_and_to_how_many():
    host = Host()

    def silent(calls, label):              # 2D's way: a person's change clears the line, then the document changes
        host.set_status("")
        host.docChanged.emit()
    hub = _hub(host, [Action("auto", "Auto layout", calls=_calls),
                      Action("group", "Group", calls=_calls, done="Grouped {what}")], silent)
    hub.run("auto")
    assert host.status == "Auto layout · 3 layers"
    hub.run("group")
    assert host.status == "Grouped 3 layers"


def test_an_apps_own_words_stay_and_no_change_says_nothing_extra():
    host = Host()

    def own(calls, label):
        host.docChanged.emit()
        host.set_status("Keyed 4 settings on 3 layers")
    hub = _hub(host, [Action("k", "Key", calls=_calls)], own)
    hub.run("k")
    assert host.status == "Keyed 4 settings on 3 layers"
    host.set_status("")
    hub2 = _hub(host, [Action("k", "Key", calls=_calls)], lambda calls, label: None)    # changed nothing
    hub2.run("k")
    assert host.status == ""


def test_the_persons_undo_flashes_what_it_took_back():
    from PySide6.QtCore import QCoreApplication
    from rostrum_core import toy
    from rostrum_gui import DocBridge
    _app = QCoreApplication.instance() or QCoreApplication([])
    bridge = DocBridge(toy.sample())
    bridge.select("cam_1")
    bridge.setValue("focal", 70)
    assert bridge.agent.flash == []               # a person's own new change: they see it already, no outline
    bridge.undo()
    assert bridge.agent.flash == ["cam_1"] and bridge.agent.flashMine
    assert bridge.status.startswith("Undid")
