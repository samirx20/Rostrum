"""Proof (S32): a person's window and an agent's MCP server share one project file, both apps, in a scratch folder.
  (a) the agent's edit_document lands in the window's document after catch_up()
  (b) a person locks a layer / track: the agent's edit on it, and on what is inside it, is refused (exact sentences)
  (c) inspect_screen returns the window's selection after LiveLink.tick()

    python shared/gui-kit/demo/s32_agent_proof.py [> proof.txt]
Runs offscreen; nothing of the person's is touched (scratch folders and settings).
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[3]
SCRATCH = tempfile.mkdtemp(prefix="rostrum-s32-")
os.environ["ROSTRUM_SETTINGS_DIR"] = SCRATCH + "/settings"
os.makedirs(SCRATCH + "/settings")
for p in ("shared/core", "shared/gui-kit", "apps/2d/python", "apps/2d/screen", "apps/sound/python", "apps/sound/screen"):
    sys.path.insert(0, str(ROOT / p))

from PySide6.QtGui import QGuiApplication  # noqa: E402
from rostrum_core import Document, Who  # noqa: E402
from rostrum_core.mcp import Runtime  # noqa: E402

AGENT, SAM = Who.agent("claude-code"), Who.person("sam")
QGuiApplication.instance() or QGuiApplication([])


def say(*a):
    print(*a, flush=True)


def line(reply):
    if reply.get("ok"):
        return reply["summary"]
    e = reply["error"]
    return f'{e["subject"]} {e["problem"]}. {e["hint"]}'.replace("·", "-")


def proof(app, folder, rt, bridge, edit, lock, locked_edits, select, shown):
    from rostrum_gui.live_link import LiveLink
    doc = bridge.doc
    say(f"\n== {app} ==")
    reply, _ = rt.call("edit_document", {"ops": [edit]}, AGENT)
    say(f"(a) agent edit_document -> ok={reply['ok']}: {line(reply)}")
    before = shown(doc)
    doc.live.catch_up()
    say(f"    window before catch_up: {before}; after: {shown(doc)}")
    doc.apply(lock, SAM)
    for what, op in locked_edits:
        reply, _ = rt.call("edit_document", {"ops": [op]}, AGENT)
        say(f"(b) agent edits {what} -> ok={reply['ok']}: {line(reply)}")
    bridge.select(select)
    link = LiveLink(bridge, app, bridge.link.state_fn)
    link._timer.stop()
    bridge.link._timer.stop()
    link.tick()
    reply, _ = rt.call("inspect_screen", {}, AGENT)
    say(f"(c) inspect_screen -> {line(reply)}")
    say(f"    selection data: {reply['data']['windows'][0]['selection']}")
    link.close()


def two_d():
    from rostrum2d import KIND, textsize
    from rostrum2d.mcp import app_tools, make_app
    from screen2d import frames
    from screen2d.bridge2d import Bridge2D

    class Fake:
        fallback = notice = None
        def load(self, scene): pass
        def still(self, t, png): pass
        def pixels(self, t, samples=None, scale=1.0): return memoryview(bytearray(64)), 4, 4, 16
        def measure(self, items): return {i["id"]: (10.0, 10.0) for i in items}
        def close(self): pass
    frames.open_engine = textsize.open_engine = Fake
    textsize._own = None
    folder = Path(SCRATCH) / "p2d"
    (folder / "docs").mkdir(parents=True)
    d = Document.new(KIND, folder=folder, item="main")
    d.apply([{"op": "comp.add", "args": {"id": "film", "fps": 10, "duration": 5}},
             {"op": "layer.add", "target": "film", "args": {"type": "shape", "id": "dot"}}], SAM)
    d.save()
    rt = Runtime(app := make_app(str(folder), ["main"]), app_tools())
    bridge = Bridge2D(Document.open(folder, "main", KIND))
    proof("2d", folder, rt, bridge, {"op": "shape.set", "target": ["dot"], "args": {"x": 321}},
          {"op": "layer.lock", "target": ["dot"]},
          [("the locked layer", {"op": "shape.set", "target": ["dot"], "args": {"x": 5}})],
          "dot", lambda doc: f'dot.x={doc.item("dot")["x"]}')
    bridge.close()


def sound():
    from rostrum_sound import KIND, run_source
    from rostrum_sound.mcp.app import make_app
    from rostrum_sound.mcp.server import make_runtime
    from screensound import playback
    from screensound.bridge import SoundBridge

    class Fake:
        def request(self, do, schedule=None, out=None, **kw):
            Path(out).write_bytes(b"")
            return {"file": out, "lufs": -20.0, "tracks": [], "stems": {}}
        def take_restarted(self): return ""
        def abort(self): pass
        def close(self): pass
    playback.open_engine = Fake
    Path(SCRATCH, "engine.exe").write_bytes(b"")
    os.environ["ROSTRUM_SOUND_ENGINE"] = SCRATCH + "/engine.exe"
    folder = Path(SCRATCH) / "psound"
    (folder / "docs").mkdir(parents=True)
    src = 'tempo(120)\nlead = track("lead", builtIn="feltPiano")\nlead.note("C4", at=beat(4), dur=beats(1))\n'
    d = Document.new(KIND, folder=folder, item="song")
    d.run_script("s.py", run_source(src, "s.py"), Who.script("s.py"))
    d.save()
    note = next(n["id"] for n in d.item("lead")["notes"])
    rt = make_runtime(make_app(str(folder), ["song"]))
    bridge = SoundBridge(Document.open(folder, "song", KIND), "Proof song")
    proof("sound", folder, rt, bridge, {"op": "track.set", "target": ["lead"], "args": {"volume": 0.4}},
          {"op": "track.lock", "target": ["lead"]},
          [("the locked track", {"op": "track.set", "target": ["lead"], "args": {"volume": 0.1}}),
           (f"a note inside it ({note})", {"op": "note.set", "target": [note], "args": {"vel": 0.2}})],
          "lead", lambda doc: f'lead.volume={doc.item("lead")["volume"]}')
    bridge.close()


if __name__ == "__main__":
    two_d()
    sound()
