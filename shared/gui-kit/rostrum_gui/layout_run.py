"""Running the layout check (layout_check.py) on an app: every scripted screen state at every real window size.

    main.py --check-layout <folder>                 # every state in the app's STATES, each in a fresh window
    main.py --check-layout <folder> --check-name n  # one state (the steps given with --step), every size; what the
                                                    # first form starts for each state
For each state and size: <folder>/<state>-<w>x<h>.png (faults boxed and numbered) and a line per fault in
<folder>/faults.txt. Fails loudly (nonzero exit, the list printed) when any state or size has a fault or a state
fails to run. A state is (name, start args, steps); a "say <words>" step puts the words in the top bar's status, as
the app would (long messages are a state too).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from . import layout_check, layout_mark

# Real windows: the smallest laptops, a common one, Sam's (1920x1080 at 117% = ~1646 wide), a full HD screen.
SIZES = [(1280, 720), (1366, 768), (1646, 900), (1920, 1080)]


def kit_step(bridge, step: str) -> bool:
    """The check's own steps (any app); True when handled:
    `say <words>`: the status line shows these words.
    `agent-run <n>`: an agent ("claude-code") makes n changes in one session, through doc.apply; the app's bridge
      gives them with the hook `agent_demo_calls(n) -> [calls, ...]` (n lists of operation calls, harmless ones).
    `agent-say <words>`: the agent chip and the message line show these words.
    `history open`: the History sheet opens (bridge.agent.historyAsked).
    `guides open [file]`, `guides find <words>`, `keylist open`, `panels fold`, `area <name>`: shell_steps.py."""
    from . import export_steps, shell_steps   # (Qt only here: the check's own process never imports them)
    word, _, rest = step.partition(" ")
    if word == "say":
        bridge._set_status(rest)
    elif word == "agent-run":
        hook = getattr(bridge, "agent_demo_calls", None)
        if hook is None:
            raise RuntimeError(f"layout step {step!r}: {type(bridge).__name__} has no agent_demo_calls(n) hook")
        from rostrum_core import Who
        for calls in hook(int(rest)):
            bridge.doc.apply(calls, Who.agent("claude-code"), session="layout-check")
    elif word == "agent-say":
        bridge.agent.say(rest)
        bridge._set_status(rest)
    elif step == "history open":
        bridge.agent.askHistory("")
    elif word in shell_steps.WORDS:
        return shell_steps.do(step)
    elif word in export_steps.WORDS:      # the Export sheet, the job and Problems chips (export_steps.py)
        return export_steps.do(bridge, step)
    else:
        return False
    return True


def sweep(app, win, out, name, ready, ignore=(), sizes=SIZES):
    """Resize `win` to each size, wait until `ready()` and the layout settles, check, mark; then exit the app
    (code 0: no fault, 5: faults). Results are added to <out>/faults.json under `name`."""
    from PySide6.QtCore import QTimer
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # a fault names on-screen words (⇄, →) on any console
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    found: dict[str, list[str]] = {}

    def step(i):
        if i == len(sizes):
            return finish()
        win.resize(*sizes[i])
        QTimer.singleShot(250, lambda: wait(i, 0))

    def wait(i, n):
        if not ready() and n < 100:
            return QTimer.singleShot(100, lambda: wait(i, n + 1))
        QTimer.singleShot(500, lambda: look(i))        # the 160 ms reveals and relayouts have finished

    def look(i):
        w, h = sizes[i]
        faults = layout_check.check(win, ignore)
        shot = out / f"{name}-{w}x{h}.png"
        layout_mark.mark(win, faults, shot)
        found[f"{w}x{h}"] = [f.line() for f in faults]
        print(f"layout {name} {w}x{h}: {len(faults)} fault(s)  {shot}")
        for k, f in enumerate(faults, 1):
            print(f"  {k:2}. {f.line()}")
        step(i + 1)

    def finish():
        from . import qt_faults                        # Qt's "not supported" warnings are faults of the state too
        if qt_faults.found():
            found["qt"] = qt_faults.found()
            print("\n".join(f"  Qt fault: {f}" for f in found["qt"]))
        record(out, name, found)
        app.exit(5 if any(found.values()) else 0)

    step(0)


def record(out: Path, name: str, found: dict):
    f = out / "faults.json"
    data = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
    data[name] = found
    f.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")


def run_all(main_py: Path, states: list[tuple[str, list[str], list[str]]], out) -> int:
    """Start the app once per state (a fresh window and document each), wait for each, write faults.txt.
    Returns the exit code: 0 only when every state ran and found nothing."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "faults.json").unlink(missing_ok=True)
    env = {**os.environ, "QT_QPA_PLATFORM": os.environ.get("QT_QPA_PLATFORM", "offscreen"),
           "QT_QPA_FONTDIR": os.environ.get("QT_QPA_FONTDIR", "C:/Windows/Fonts")}
    broken = []
    for name, start, steps in states:
        cmd = [sys.executable, str(main_py), *start, *sum((["--step", s] for s in steps), []),
               "--check-layout", str(out), "--check-name", name]
        r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)
        print(r.stdout, end="")
        if r.returncode not in (0, 5):
            broken.append(f"{name}: the state did not run (exit {r.returncode}): {r.stderr.strip()[-600:]}")
    data = json.loads((out / "faults.json").read_text(encoding="utf-8")) if (out / "faults.json").is_file() else {}
    lines = [f"{name} {size}: {line}" for name, sizes in data.items() for size, ls in sizes.items() for line in ls]
    (out / "faults.txt").write_text("\n".join(broken + lines) + "\n", encoding="utf-8")
    total = len(lines)
    print(f"\nlayout check: {len(states)} states x {len(SIZES)} sizes, {total} fault(s), {len(broken)} state(s) failed"
          f" -> {out / 'faults.txt'}")
    for b in broken:
        print(f"FAIL: {b}", file=sys.stderr)
    return 0 if not total and not broken else 5
