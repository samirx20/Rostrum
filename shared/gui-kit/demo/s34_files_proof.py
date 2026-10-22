"""Proof (S34, kit piece 13): a project opened the way ≡ › Open does is live in both apps, so an agent's change made
through its own copy of the document (as the MCP server does: Document.open + live.keep) shows in the window after the
window's LiveLink tick, with nothing saved by hand. Each app runs in its own process, one after the other.

    python shared/gui-kit/demo/s34_files_proof.py <out folder>        # both apps: <out>/proof.txt, 2d-*.png, sound-*.png
    python shared/gui-kit/demo/s34_files_proof.py <out folder> 2d     # one app (what the parent runs)
Offscreen; scratch projects and settings only (a scripted run never touches the person's; userhome.py).
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def both(out: Path):
    sys.stdout.reconfigure(encoding="utf-8")
    out.mkdir(parents=True, exist_ok=True)
    lines = []
    for app in ("2d", "sound"):
        p = subprocess.run([sys.executable, __file__, str(out), app], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        lines += [l for l in p.stdout.splitlines()] + [f"   ({app}: exit {p.returncode})"]
        warn = [l for l in p.stderr.splitlines() if l.startswith(("QML", "FAIL", "Traceback", "AssertionError"))]
        lines += [f"   stderr: {w}" for w in warn]
        if p.returncode:
            lines += p.stderr.splitlines()[-15:]
    (out / "proof.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if "exit 1" not in "\n".join(lines) and all("exit 0" in l for l in lines if "exit" in l) else 1


def one(out: Path, app: str):
    sys.stdout.reconfigure(encoding="utf-8")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    scratch = Path(tempfile.mkdtemp(prefix=f"rostrum-s34-{app}-"))
    os.environ["ROSTRUM_PROJECTS_DIR"] = str(scratch / "projects")
    screen = ROOT / "apps" / app / "screen"
    for p in ("shared/core", "shared/gui-kit", f"apps/{app}/python", f"apps/{app}/screen"):
        sys.path.insert(0, str(ROOT / p))
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QGuiApplication
    from rostrum_core import Document, Who, live
    app_ = QGuiApplication.instance() or QGuiApplication([])
    say = lambda *a: print(*a, flush=True)  # noqa: E731

    if app == "2d":
        from rostrum2d import KIND
        from screen2d.files2d import blank
        from screen2d.session import Session
        host = Session((1600, 960))
        made = blank(scratch / "projects" / "Proof film")
        made.apply([{"op": "layer.add", "target": "main", "args": {"type": "shape", "id": "dot"}},
                    {"op": "shape.set", "target": ["dot"], "args": {"x": 400, "y": 540, "w": 240, "h": 240,
                                                                    "fill": "#4c8dff"}}], Who.person("sam"))
        made.save()
        agent_op = {"op": "shape.set", "target": ["dot"], "args": {"x": 1320, "fill": "#ff7a59"}}
        seen = lambda b: f'dot.x={b.doc.item("dot")["x"]}, dot.fill={b.doc.item("dot")["fill"]}'  # noqa: E731
        ready = lambda b: b.frames.idle() and b.frame > 0  # noqa: E731
    else:
        from rostrum_sound import KIND
        sys.argv = [str(screen / "main.py")]
        import importlib.util
        spec = importlib.util.spec_from_file_location("sound_main", screen / "main.py")
        sound_main = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sound_main)
        from screensound.files_sound import blank
        host = sound_main.Screen((1600, 960))
        made = blank(scratch / "projects" / "Proof song")
        agent_op = {"op": "track.add", "args": {"id": "keys", "name": "Keys"}}
        seen = lambda b: f'tracks={[r["name"] for r in b.tracks if not r.get("mix")]}'  # noqa: E731
        ready = lambda b: not b.transport.busy()  # noqa: E731
    files = host.files
    say(f"== {app} ==")
    files.launch()
    say(f"launch with nothing to reopen: start screen shown={files.startShown}, a project open={files.hasProject}")
    ok = files.openPath(str(made.folder))                               # what ≡ › Open does with a picked folder
    bridge = host.bridge
    say(f"≡ › Open {made.folder.name}: ok={ok}; the window's document is live={bridge.doc.live is not None}; "
        f'top bar says "{bridge.isLive and "Saved"}"; start screen shown={files.startShown}')
    say(f"window before the agent: {seen(bridge)}")
    server = Document.open(made.folder, made.item_id, KIND)            # the MCP server's own copy
    live.keep(server)
    server.apply(agent_op, Who.agent("claude-code"), session="proof-run")
    say(f"agent (its own live copy) applied {agent_op['op']}; window still shows: {seen(bridge)}")
    bridge.link.tick()                                                 # the window's LiveLink timer, once
    say(f"window after its LiveLink tick: {seen(bridge)}; agent chip: {bridge.agent.chip['text']!r}")
    on_disk = Document.open(made.folder, made.item_id, KIND)
    say(f"on disk with nothing saved by hand: seq={on_disk.seq}, same as the window's={on_disk.seq == bridge.doc.seq}")
    assert bridge.doc.data == server.data, "the window did not catch up with the agent's change"
    bridge.doc.apply(agent_op if app == "2d" else {"op": "track.set", "target": ["keys"], "args": {"mute": True}},
                     Who.person("sam"))
    say(f"a person's change in the window is on disk at once: "
        f"{Document.open(made.folder, made.item_id, KIND).seq == bridge.doc.seq}")
    ok = files.duplicate("Proof copy")
    say(f'Duplicate "Proof copy": ok={ok}; window stays on {files.name!r}; message: "{bridge.status}"')
    shot = out / f"{app}-window-after-agent.png"

    def wait(n=0):
        if ready(bridge) or n > 150:
            QTimer.singleShot(700, grab)
        else:
            QTimer.singleShot(100, lambda: wait(n + 1))

    def grab():
        img = host.win.grabWindow()
        say(f"picture: {shot} saved={img.save(str(shot))}")
        app_.exit(0)
    QTimer.singleShot(300, wait)
    app_.exec()
    host.close()
    import shutil
    shutil.rmtree(scratch, ignore_errors=True)                         # the scratch projects go with the run


if __name__ == "__main__":
    if len(sys.argv) > 2:
        one(Path(sys.argv[1]), sys.argv[2])
    else:
        sys.exit(both(Path(sys.argv[1])))
