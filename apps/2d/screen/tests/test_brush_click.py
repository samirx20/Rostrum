"""A new piece opens with nothing picked (the scene: a first drag never moves the frame), and a real click on the
Brush icon opens the brush panel at once. Its first opening once froze the app for good: the panel's strokes were
read on Qt's loader thread, which waited for Python's lock while the click held it (rostrum_gui/screen_images.py).
A frozen app can't even exit, so the click runs in a child process the test ends after a time limit."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
SCREEN = Path(__file__).resolve().parents[1]


def _child(folder):
    sys.path[:0] = [str(ROOT), str(SCREEN)]
    import checkout_paths
    checkout_paths.use_this_checkout()
    from PySide6.QtCore import QObject
    from rostrum_gui.app import qt_app
    from screen2d.click_steps import do_click_step
    from screen2d.files2d import blank
    from screen2d.session import Session
    app = qt_app()
    session = Session((1646, 900), None)
    session.files.put(blank(Path(folder)))                 # as New makes it: a scene and its frame
    b = session.bridge
    print("picked:", "scene" if b._sel == b.comp_id else b._sel, flush=True)
    do_click_step(session.win, "clickobj", ["rail_brush"], "clickobj rail_brush")   # a real press and release
    fly = session.win.findChild(QObject, "brushFlyout")
    print("panel:", "open" if fly is not None and fly.property("opened") else "closed", "tool:", b.tool, flush=True)
    app.processEvents()
    session.close()


def test_a_new_piece_picks_nothing_and_a_real_brush_click_opens_the_panel(tmp_path):
    from rostrum2d import settings
    if settings.engine_missing_reason() is not None:
        pytest.skip(settings.engine_missing_reason())
    child = subprocess.Popen([sys.executable, __file__, str(tmp_path)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             text=True, env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    try:
        out = child.communicate(timeout=60)[0]
    except subprocess.TimeoutExpired:
        if os.name == "nt":                                  # the child and the engines it started
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(child.pid)], capture_output=True)
        child.kill()
        child.communicate()
        pytest.fail("the Brush click froze the app (no answer in 60 s)")
    assert "picked: scene" in out, out
    assert "panel: open tool: draw" in out, out


if __name__ == "__main__":
    _child(sys.argv[1])
