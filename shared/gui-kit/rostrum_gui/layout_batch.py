"""Many layout-check states in one app process (layout_run.run_all starts one per batch, not one per state).

Starting the app costs ~9 s (imports, the drawing engine); a state's four sizes cost ~3 s. So a batch process starts
once and shows each state's document the way File > Open does (a new window and bridge per document, the old ones
closed), then runs that state's steps and sweep. Between states the scratch settings home is emptied, so no state
sees another's Open recent, saved brushes or remembered places.

    main.py --check-layout <folder> --check-batch <states.json>     (the parent writes the file; run_all)
    states.json: [[name, start args, steps], ...]; the child prints `layout-start <name>` and `layout-done <name>`
    around each, so the parent knows which state a dead child was on.

`batch(app, states_file, out, open_, steps, window, ready, ignore)`: open_(start args) shows the state's document;
steps(list) runs its steps; window() is the current window; ready() the app's "newest frame has landed"; ignore the
app's deliberate faults.
"""
from __future__ import annotations

import gc
import json
import shutil
import sys
import traceback
from pathlib import Path

PER_STATE_S = 150          # a state that takes longer is stuck: the child ends (exit 4), the parent moves on


def clear_home() -> None:
    """Empty the scratch settings home (never the person's: only a scripted run gets here)."""
    from rostrum_core import userhome
    if not userhome.scripted():
        raise RuntimeError("layout batch: refusing to empty a person's settings home")
    home = userhome.home()
    home.mkdir(parents=True, exist_ok=True)
    for p in home.iterdir():
        shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)


def batch(app, states_file, out, open_, steps, window, ready, ignore=()) -> None:
    from PySide6.QtCore import QTimer
    from . import layout_run
    todo = [tuple(s) for s in json.loads(Path(states_file).read_text(encoding="utf-8"))]
    worst = [0]
    dog = [None]

    def next_state(code=0):
        worst[0] = max(worst[0], code)
        if dog[0] is not None:
            dog[0].stop()
        if not todo:
            return app.exit(worst[0])
        name, start, run = todo.pop(0)
        print(f"layout-start {name}", flush=True)
        dog[0] = timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: (print(f"FAIL: timeout: {name} ran over {PER_STATE_S} s", file=sys.stderr), app.exit(4)))
        timer.start(PER_STATE_S * 1000)
        try:
            clear_home()
            gc.collect()                  # the last window's Python wrappers go now, not in the middle of this one's check
            open_(start)
        except Exception as e:  # noqa: BLE001  a state that cannot open is reported; the parent goes on with the rest
            return fail(name, e)
        QTimer.singleShot(400, lambda: go(name, run))

    def go(name, run):
        try:
            steps(run)
            layout_run.sweep(app, window(), out, name, ready, ignore, then=lambda code: done(name, code))
        except Exception as e:  # noqa: BLE001
            fail(name, e)

    def done(name, code):
        print(f"layout-done {name}", flush=True)
        next_state(code)

    def fail(name, e):
        print(f"FAIL: {name}: {e}\n{traceback.format_exc()}", file=sys.stderr)
        app.exit(3)

    QTimer.singleShot(0, next_state)          # (an exit before the event loop runs is lost)
