"""Proof: Sound's own action list (team-priyam's P27, read only) through the kit adapter, ActionHub, ContextBar,
ActionMenu and CommandBar, on a real Sound song. Needs the team-priyam worktree next to this one.

    python shared/gui-kit/demo/sound_proof.py [out folder]
Saves PNGs: one clip, two clips (bar, right-click, Ctrl+K), one note, three notes (same), then quits.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOUND = Path(r"C:\Users\Sam\.t3\worktrees\Rostrum\team-priyam\apps\sound")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Sam\.rostrum\waves\results\kit\s31\sound")
for p in (HERE.parent, SOUND / "python", SOUND / "screen"):
    sys.path.insert(0, str(p))

from PySide6.QtCore import Property, QMetaObject, QObject, QTimer, Signal  # noqa: E402

from rostrum_core import Document  # noqa: E402
from rostrum_gui import start  # noqa: E402
from rostrum_gui.action_adapt import from_dicts  # noqa: E402
from rostrum_gui.action_hub import ActionHub  # noqa: E402
from rostrum_gui.actions import ActionList, plural  # noqa: E402
from rostrum_gui.keymap import KeyMap  # noqa: E402
from sound_keys import SOUND_KEYS  # noqa: E402
from rostrum_sound import KIND, run_source  # noqa: E402
from rostrum_sound.doc import select_time as ST  # noqa: E402
from screensound.action_calls import Facts  # noqa: E402
from screensound.actions import ACTIONS  # noqa: E402
from screensound.sample import DOOR  # noqa: E402

NEEDS_TWO = ("sel:group", "sel:layer")      # what P27's dicts should carry themselves: min_targets 2 (the kit's guard)


def with_counts(actions):
    return [{**a, "min_targets": 2} if a["key"] in NEEDS_TWO else a for a in actions]

SOURCE = f'''
tempo(100); beats_per_bar(4); length(bar(9))
lead = track("melody", model="guitar", position=0.2, volume=0.8)
for n, p in enumerate(["D4", "F4", "A4", "G4", "F4", "E4", "D4", "C4"]):
    lead.note(p, at=beat(n), dur=beats(1), vel=0.7)
door = track("door", volume=0.9)
door.clip(r"{DOOR}", at=0.5)
door.clip(r"{DOOR}", at=4.0)
foley = track("foley", volume=0.9)
foley.clip(r"{DOOR}", at=2.0)
'''


class Scene(QObject):
    changed = Signal()

    def __init__(self, doc):
        super().__init__()
        self.doc, self.ids = doc, []

    def facts(self):
        return Facts(self.doc, self.ids)

    @Property("QVariantList", constant=True)
    def rows(self):
        root, out = self.doc.data, []
        for t in root["tracks"]:
            items = []
            for it in t["notes"] + t["clips"]:
                a, b = ST.start_of(root, it), ST.end_of(root, it)
                pitch = it.get("pitch", "")
                midi = 12 * (int(pitch[-1]) + 1) + {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[pitch[0]] if pitch else 0
                items.append({"id": it["id"], "type": it["type"], "x": a * 120, "w": (b - a) * 120, "pitch": midi})
            out.append({"name": t["name"], "items": items})
        return out

    @Property("QVariantList", notify=changed)
    def selected(self):
        return self.ids

    def pick(self, ids):
        self.ids = list(ids)
        self.changed.emit()


def what(f):
    """"3 clips": how the bar says what is selected."""
    if not f.count:
        return ""
    if len(f.kinds) != 1:
        return f"{f.count} things"
    kind = next(iter(f.kinds))
    return f"1 {kind}" if f.count == 1 else f"{f.count} {plural(kind)}"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    doc = Document(KIND, run_source(SOURCE, "proof"))
    scene = Scene(doc)
    keymap = KeyMap("Sound", SOUND_KEYS)
    hub = ActionHub(ActionList(from_dicts(with_counts(ACTIONS), keymap), keymap, noun="item"), scene.facts, what,
                    lambda calls, label: print("apply", label, calls), lambda do, e: print("do", do, e["id"]),
                    lambda m: print("message:", m))
    app, engine, win = start(HERE / "qml" / "SoundProof.qml", {"scene": scene, "actions": hub}, (1280, 720))
    clips = [i["id"] for t in doc.data["tracks"] for i in t["clips"]]
    notes = [i["id"] for t in doc.data["tracks"] for i in t["notes"]]
    shots = [("clip-1", clips[:1], None), ("clips-2", clips[:2], None), ("clips-2-menu", clips[:2], "showMenu"),
             ("clips-2-keys", clips[:2], "showCommands"), ("note-1", notes[:1], None), ("notes-3", notes[:3], None),
             ("notes-3-menu", notes[:3], "showMenu"), ("notes-3-keys", notes[:3], "showCommands")]
    state = {"i": 0}

    def step():
        name, ids, door = shots[state["i"]]
        QMetaObject.invokeMethod(win, "closeAll")
        scene.pick(ids)
        hub.refresh()
        if door:
            QMetaObject.invokeMethod(win, door)
        QTimer.singleShot(600, lambda: snap(name))

    def snap(name):
        img = win.grabWindow()
        if img.isNull() or not img.save(str(OUT / f"{name}.png")):
            print("FAIL: could not save", name, file=sys.stderr)
            app.exit(3)
            return
        bar = hub.bar
        print(name, "|", bar["what"], "|", [i["label"] for i in bar["items"]], "| more:", [m["label"] for m in bar["more"]])
        state["i"] += 1
        if state["i"] < len(shots):
            QTimer.singleShot(100, step)
        else:
            app.quit()

    QTimer.singleShot(500, step)
    QTimer.singleShot(30000, lambda: (print("FAIL: timeout", file=sys.stderr), app.exit(4)))
    app.exec()
    del engine


if __name__ == "__main__":
    main()
