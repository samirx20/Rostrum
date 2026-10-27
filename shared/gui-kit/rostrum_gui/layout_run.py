"""Running the layout check (layout_check.py) on an app: every scripted screen state at every real window size.

    main.py --check-layout <folder>                 # every state in the app's STATES, four sizes
    main.py --check-layout <folder> --quick         # the app's QUICK states at 1646x900 only: ~2 min, run before reporting
    main.py --check-layout <folder> --check-only a,b  # only these states (re-check a fault this way)
    main.py --check-layout <folder> --check-name n  # one state in this process (the steps given with --step), every size
For each state and size: <folder>/<state>-<w>x<h>.png (faults boxed and numbered) and a line per fault in
<folder>/faults.txt. Fails loudly (nonzero exit, the list printed) when any state or size has a fault or a state
fails to run. A state is (name, start args, steps); a "say <words>" step puts the words in the top bar's status, as
the app would (long messages are a state too).
The states run BATCH to a process (layout_batch.py: the app starts once, each state opens like File > Open, the scratch
settings home emptied between); a state that kills its process is reported and the rest go on. Where the time goes
(ROSTRUM_CHECK_TIMING=1 prints it per state): the app's start ~9 s (imports 3 s, the engine and first frame 4 s), then
per state its open and steps, then ~1.5 s per size (settle, check, picture).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import layout_check, layout_mark, qt_faults

# Real windows: the smallest laptops, a common one, Sam's (1920x1080 at 117% = ~1646 wide), a full HD screen.
SIZES = [(1280, 720), (1366, 768), (1646, 900), (1920, 1080)]
SAM = SIZES[2]           # the quick check's one size
BATCH = 12               # states to a process (the app grows slower as it opens one document after another)
BATCH_TIMEOUT_S = 1800
RESIZE_PAUSE_MS = 250    # after a resize, before settling: the canvas redraws sharp 150 ms later (Stage.qml's settle Timer);
                         # without this the picture can be the old frame scaled (a 1-px blur at 1920)


def kit_step(bridge, step: str) -> bool:
    """The check's own steps (any app); True when handled:
    `say <words>`: the status line shows these words.
    `agent-run <n>`: an agent ("claude-code") makes n changes in one session, through doc.apply; the app's bridge
      gives them with the hook `agent_demo_calls(n) -> [calls, ...]` (n lists of operation calls, harmless ones).
    `agent-say <words>`: the agent chip and the message line show these words.
    `history open`: the History sheet opens (bridge.agent.historyAsked).
    `selecttime <id> <id> … [n] [profile]`: the cost of switching the selection (select_steps.py).
    `clicktime <x>,<y> <x>,<y> … [n] [profile]`: the same for real mouse clicks at those window points (select_steps.py).
    `guides open [file]`, `guides find <words>`, `keylist open`, `panels fold`, `area <name>`: shell_steps.py."""
    from . import export_steps, select_steps, shell_steps   # (Qt only here: the check's own process never imports them)
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
    elif word == "selecttime":
        select_steps.do(bridge, rest.split())
    elif word == "clicktime":
        select_steps.clicks(shell_steps.window(), rest.split())
    elif step == "history open":
        bridge.agent.askHistory("")
    elif word in shell_steps.WORDS:
        return shell_steps.do(step)
    elif word in export_steps.WORDS:      # the Export sheet, the job and Problems chips (export_steps.py)
        return export_steps.do(bridge, step)
    else:
        return False
    return True


def wanted_sizes():
    """SIZES, or just those named in ROSTRUM_CHECK_SIZES ("1646x900", comma-separated: the quick check)."""
    named = os.environ.get("ROSTRUM_CHECK_SIZES")
    return [tuple(int(n) for n in s.split("x")) for s in named.split(",")] if named else SIZES


def sweep(app, win, out, name, ready, ignore=(), sizes=None, then=None):
    """Resize `win` to each size, wait until `ready()` and the layout settles, check, mark; then exit the app
    (code 0: no fault, 5: faults) or, given `then`, call then(code) (layout_batch.py: the next state follows).
    Results are added to <out>/faults.json under `name`."""
    sizes = sizes or wanted_sizes()
    from PySide6.QtCore import QTimer
    from .settle import settle
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # a fault names on-screen words (⇄, →) on any console
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    found: dict[str, list[str]] = {}
    seen_qt = len(qt_faults.found())
    clock = Timing(name)

    def step(i):
        if i == len(sizes):
            return finish()
        clock.lap("pause" if i == 0 else "mark")
        win.resize(*sizes[i])
        QTimer.singleShot(RESIZE_PAUSE_MS, lambda: wait(i))

    def wait(i):                     # frames until the newest frame has landed and the screen holds still (settle.py)
        clock.lap("resize")
        settle(win, lambda img: look(i), lambda why: unsettled(i, why), ready=ready)

    def unsettled(i, why):
        w, h = sizes[i]
        found[f"{w}x{h}"] = [why]
        print(f"layout {name} {w}x{h}: FAIL {why}")
        step(i + 1)

    def look(i):
        w, h = sizes[i]
        clock.lap("settle")
        faults = layout_check.check(win, ignore)
        clock.lap("check")
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
        clock.lap("mark")
        record(out, name, found)
        clock.report()
        code = 5 if any(found.values()) else 0
        then(code) if then else app.exit(code)

    step(0)


class Timing:
    """ROSTRUM_CHECK_TIMING=1: seconds per phase of one state's sweep, printed as `timing <state> <phase>=<s> ...`."""
    def __init__(self, name):
        self.name, self.on, self.t, self.sum = name, bool(os.environ.get("ROSTRUM_CHECK_TIMING")), time.monotonic(), {}
        if os.environ.get("ROSTRUM_CHECK_T0"):       # set by the run that started this process
            self.sum["boot+steps"] = time.time() - float(os.environ["ROSTRUM_CHECK_T0"])

    def lap(self, phase):
        now = time.monotonic()
        self.sum[phase] = self.sum.get(phase, 0) + now - self.t
        self.t = now

    def report(self):
        if self.on:
            print(f"timing {self.name} " + " ".join(f"{k}={v:.2f}" for k, v in self.sum.items()))


def record(out: Path, name: str, found: dict):
    f = out / "faults.json"
    data = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
    data[name] = found
    f.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")


def run_all(main_py: Path, states: list[tuple[str, list[str], list[str]]], out, only: str | None = None,
            quick: bool = False, origin: str = "builtin") -> int:
    """Run the states, `BATCH` to a process (the app starts once per batch: layout_batch.py), write faults.txt.
    `only`: comma-separated state names, just those (an unknown name fails loudly). `quick`: the app's QUICK states at
    Sam's size only. A state that kills its batch (a crash, a Qt fault, a hang) is reported as not run, and the rest
    go on in a new one. `origin`: where these states come from ("builtin", or a plugin's id): a fault of a plugin's
    state is written with it, so the fault is the plugin's to fix. Returns the exit code: 0 only when every state ran and found nothing."""
    if quick:
        os.environ["ROSTRUM_CHECK_SIZES"] = "x".join(str(n) for n in SAM)
    if only:
        names = [n.strip() for n in only.split(",") if n.strip()]
        unknown = sorted(set(names) - {s[0] for s in states})
        if unknown:
            raise SystemExit(f"layout check: no state named {', '.join(unknown)}")
        states = [s for s in states if s[0] in names]
    elif quick:
        names = set(app_states(main_py).QUICK)
        states = [s for s in states if s[0] in names]
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "faults.json").unlink(missing_ok=True)
    from .app import offscreen_env
    env = {**offscreen_env(), **os.environ}
    batch = getattr(app_states(main_py), "BATCH", BATCH)
    broken, started, pending = [], time.time(), list(states)
    while pending:
        group, pending = pending[:batch], pending[batch:]
        r, last, err = run_group(main_py, group, out, env)
        if r not in (0, 5):
            culprit = last or group[0][0]
            broken.append(f"{culprit}: the state did not run (exit {r}): {err[-600:]}")
            pending[:0] = [s for s in group if s[0] != culprit and not done_in(out, s[0])]
    data = json.loads((out / "faults.json").read_text(encoding="utf-8")) if (out / "faults.json").is_file() else {}
    who = "" if origin == "builtin" or origin.startswith("builtin:") else f"[{origin}] "
    broken = [who + b for b in broken]
    lines = [f"{who}{name} {size}: {line}" for name, sizes in data.items() for size, ls in sizes.items() for line in ls]
    (out / "faults.txt").write_text("\n".join(broken + lines) + "\n", encoding="utf-8")
    total = len(lines)
    print(f"\nlayout check: {len(states)} states x {len(wanted_sizes())} sizes, {total} fault(s), {len(broken)} state(s) failed"
          f" in {time.time() - started:.0f} s -> {out / 'faults.txt'}")
    for b in broken:
        print(f"FAIL: {b}", file=sys.stderr)
    return 0 if not total and not broken else 5


def done_in(out: Path, name: str) -> bool:
    f = out / "faults.json"
    return f.is_file() and name in json.loads(f.read_text(encoding="utf-8"))


def app_states(main_py: Path):
    """The app's layout_states module (QUICK: its most important states; BATCH: states to a process, if it says)."""
    import importlib
    sys.path.insert(0, str(main_py.parent))
    pkg = next(p.name for p in main_py.parent.iterdir() if (p / "layout_states.py").is_file())
    return importlib.import_module(f"{pkg}.layout_states")


def run_group(main_py: Path, group, out: Path, env) -> tuple[int, str, str]:
    """One child process for `group`: (exit code, the state it was on when it ended, its stderr)."""
    with tempfile.TemporaryDirectory(prefix="rostrum-state-") as home:      # its own settings and library
        listing = Path(home) / "states.json"
        listing.write_text(json.dumps(group), encoding="utf-8")
        cmd = [sys.executable, str(main_py), "--check-layout", str(out), "--check-batch", str(listing)]
        r = subprocess.run(cmd, env={**env, "ROSTRUM_SCRIPTED_HOME": str(Path(home) / "settings"),
                                     "ROSTRUM_CHECK_T0": str(time.time()),
                                     "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},    # the child writes UTF-8 ...
                           capture_output=True, text=True, encoding="utf-8", errors="replace",   # ... and we read it so
                           timeout=BATCH_TIMEOUT_S)
    print(r.stdout.replace("layout-start ", "start ").replace("layout-done ", "done "), end="")
    started = [ln.split(" ", 1)[1] for ln in r.stdout.splitlines() if ln.startswith("layout-start ")]
    ended = {ln.split(" ", 1)[1] for ln in r.stdout.splitlines() if ln.startswith("layout-done ")}
    return r.returncode, next((n for n in reversed(started) if n not in ended), ""), r.stderr.strip()
