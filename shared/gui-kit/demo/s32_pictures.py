"""Real-app pictures for S32: a person's window and an agent's MCP server on one scratch project; the agent chip working
with the 1-second outline, done, History with the run folded, after Undo all, and after the person's Ctrl+Z.

    python shared/gui-kit/demo/s32_pictures.py 2d|sound [out folder]      (offscreen; scratch project and settings)
Writes a.png .. e.png and captions.md in the out folder (default: waves/results/kit/s32/<app>).
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")
APP = sys.argv[1]
ROOT = Path(__file__).resolve().parents[3]
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else rf"C:\Users\Sam\.rostrum\waves\results\kit\s32\{APP}")
OUT.mkdir(parents=True, exist_ok=True)
SCRATCH = tempfile.mkdtemp(prefix="rostrum-s32pic-")
os.environ["ROSTRUM_SETTINGS_DIR"] = SCRATCH + "/settings"
os.makedirs(SCRATCH + "/settings")
for p in ("shared/core", "shared/gui-kit", "apps/2d/python", "apps/2d/screen", "apps/sound/python", "apps/sound/screen"):
    sys.path.insert(0, str(ROOT / p))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from rostrum_core import Document, Who  # noqa: E402
from rostrum_core.mcp import Runtime  # noqa: E402

AGENT = Who.agent("claude-code")
app = QGuiApplication.instance() or QGuiApplication(sys.argv)
folder = Path(SCRATCH) / "project"
(folder / "docs").mkdir(parents=True)
notes: list[str] = []


def say(text):
    notes.append(text)
    print(text, flush=True)


if APP == "2d":
    from rostrum2d import KIND, run_source
    from rostrum2d.mcp import app_tools, make_app
    from screen2d.sample import SOURCE
    from screen2d.session import Session
    ITEM = "main"
    d = Document.new(KIND, folder=folder, item=ITEM)
    d.run_script("sample.py", run_source(SOURCE, "sample.py"))
    d.save()
    rt = Runtime(make_app(str(folder), [ITEM]), app_tools())
    ui = Session((1600, 960))
    ui.show(Document.open(folder, ITEM, KIND), live=True)
    run = [{"op": "text.set", "target": ["title"], "args": {"x": 700}},
           {"op": "shape.set", "target": ["card"], "args": {"fill": "#2a3a66"}},
           {"op": "shape.set", "target": ["rule"], "args": {"w": 300}}]
    person, agent2 = ({"op": "shape.set", "target": ["card"], "args": {"radius": 8}},
                      {"op": "text.set", "target": ["title"], "args": {"size": 140}})
    watch = lambda doc: f'card.radius={doc.item("card").get("radius")}, title.size={doc.item("title").get("size")}'
    ready = lambda b: b.frames.idle() and b.frame > 0
else:
    os.environ.setdefault("ROSTRUM_SOUND_ENGINE", r"C:\Users\Sam\Documents\CODE\Rostrum\apps\sound\engine\target\agent\rostrum-sound.exe")
    from rostrum_sound import KIND, run_source
    from rostrum_sound.mcp.app import make_app
    from rostrum_sound.mcp.server import make_runtime
    from screensound.sample import SOURCE
    sys.path.insert(0, str(ROOT / "apps/sound/screen"))
    import importlib.util
    spec = importlib.util.spec_from_file_location("sound_main", ROOT / "apps/sound/screen/main.py")
    sound_main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sound_main)
    ITEM = "song"
    d = Document.new(KIND, folder=folder, item=ITEM)
    d.run_script("sample.py", run_source(SOURCE, "sample.py"))
    d.save()
    rt = make_runtime(make_app(str(folder), [ITEM]))
    ui = sound_main.Screen((1600, 960))
    ui.songs.start(Document.open(folder, ITEM, KIND), "")
    run = [{"op": "track.set", "target": ["melody"], "args": {"volume": 0.6}},
           {"op": "track.set", "target": ["pad"], "args": {"volume": 0.4}},
           {"op": "track.set", "target": ["drums"], "args": {"volume": 0.5}}]
    person, agent2 = ({"op": "track.set", "target": ["melody"], "args": {"pan": -0.5}},
                      {"op": "track.set", "target": ["pad"], "args": {"pan": 0.4}})
    watch = lambda doc: f'melody.pan={doc.item("melody").get("pan")}, pad.pan={doc.item("pad").get("pan")}'
    ready = lambda b: not b.transport.busy()

state = {"session": ""}


def bridge():
    return ui.bridge


def snap(name):
    img = ui.win.grabWindow()
    img.save(str(OUT / f"{name}.png"))
    print("saved", name, flush=True)


def agent_do(calls):
    for c in calls:
        reply, _ = rt.call("edit_document", {"ops": [c]}, AGENT)
        assert reply["ok"], reply
    bridge().link.tick()                    # the window takes the steps in (LiveLink's timer does it every 300 ms)


def step_a():
    say(f"Start: {watch(bridge().doc)}")
    agent_do(run)
    state["session"] = bridge().agent.chip["session"]
    say(f"(a) the agent made {len(run)} edits through its MCP server; the chip: {bridge().agent.chip}")


def step_c():
    bridge().agent.askHistory("")


def step_d():
    bridge().undoRun(state["session"])
    say(f"(d) Undo all from History; status: {bridge().status}")


def step_e():
    ui.win.setProperty("historyOpen", False)
    b = bridge()
    before = watch(b.doc)
    b.doc.apply(person, b.who)
    after_person = watch(b.doc)
    agent_do([agent2])
    after_agent = watch(b.doc)
    b.undo()                                # Ctrl+Z
    after_undo = watch(b.doc)
    say(f"(e) before: {before}\n    after the person's edit: {after_person}\n    after the agent's edit: {after_agent}\n"
        f"    after Ctrl+Z (the person's own step): {after_undo}   <- the person's edit is gone, the agent's is kept")


def finish():
    (OUT / "captions.md").write_text(
        f"# S32 pictures, {APP}\n\n"
        "- a.png: the agent chip working (\"Claude is working · 3 changes\") and the 1-second outline round what it changed.\n"
        "- b.png: 5 seconds later: \"Claude: 3 changes · Review · Keep · Undo all\".\n"
        "- c.png: History with the agent's run as one folded row.\n"
        "- d.png: after Undo all in History: the run shows taken back, the document is back.\n"
        "- e.png: the person's own edit, then an agent edit, then Ctrl+Z: the person's edit is gone, the agent's kept.\n\n"
        "```\n" + "\n".join(notes) + "\n```\n", encoding="utf-8")
    app.exit(0)


def wait_ready(then, n=0):
    if ready(bridge()) or n > 100:
        QTimer.singleShot(700, then)
    else:
        QTimer.singleShot(100, lambda: wait_ready(then, n + 1))


def seq(steps):
    if not steps:
        return
    (delay, fn), rest = steps[0], steps[1:]
    def go():
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            print(f"FAIL: {e!r}", file=sys.stderr)
            app.exit(3)
            return
        seq(rest)
    QTimer.singleShot(delay, go)


QTimer.singleShot(300, lambda: wait_ready(lambda: seq([
    (0, lambda: APP == "2d" and bridge().setTime(1.2)),      # the person's playhead: the titles are on screen
    (1200, step_a), (250, lambda: snap("a")),
    (5600, lambda: snap("b")),
    (0, step_c), (500, lambda: snap("c")),
    (0, step_d), (500, lambda: snap("d")),
    (0, step_e), (600, lambda: snap("e")),
    (0, finish)])))
QTimer.singleShot(150000, lambda: (print("FAIL: timeout", file=sys.stderr), app.exit(4)))
code = app.exec()
bridge().link.close()
sys.exit(code)
