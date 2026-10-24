"""Is another job using the graphics card right now? (SPEC §11.2 point 3: the estimate says so.)

`busy(own_pids)` samples the card's load three times with `nvidia-smi` (about 0.5 s; up to 2 s when the driver was
asleep) and returns "" (free, or no NVIDIA tool: a Mac, another card) or one plain sentence for the person or agent.
The load decides, not the list of programs on the card: an idle engine that keeps the card open (a 2D render engine,
the window's own Storm viewport) is listed but costs nothing. On the reference laptop an idle desktop with such
engines open reads 0-10 %; a Cycles render reads 90-100 %, so the line is at 40 % (the middle sample, so one spike
does not fire it). The card does not say which program makes the load (Windows), so when it is busy and every program
on it is one of `own_pids` (the window's own viewport, say, running Look: Final), the load is ours and nothing is
said. Call it BEFORE starting your own probe, or your own render is counted.
"""
from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import PureWindowsPath

BUSY_PCT = 40
SAMPLES, GAP_S = 3, 0.15


def _smi(*query: str) -> str | None:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        return subprocess.run([exe, *query, "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except (OSError, subprocess.SubprocessError):
        return None


def load_pct() -> int | None:
    """The card's load now (0-100; several cards: the busiest), or None when it cannot be read."""
    try:
        return max(int(x) for x in (_smi("--query-gpu=utilization.gpu") or "").split())
    except ValueError:
        return None


def programs() -> dict[int, str]:
    """{pid: program name} of the programs using the card for computing (empty when it cannot be read)."""
    out = {}
    for line in (_smi("--query-compute-apps=pid,process_name") or "").splitlines():
        pid, _, name = line.partition(",")
        if pid.strip().isdigit():
            out[int(pid)] = PureWindowsPath(name.strip()).name
    return out


def busy(own_pids=(), read=load_pct, apps=programs, samples: int = SAMPLES, gap_s: float = GAP_S) -> str:
    """"" or "Another job is using the graphics card (87 % busy: rostrum3d-core.exe): renders are slower now, about 2× while it runs."."""
    seen = []
    for n in range(samples):
        if (p := read()) is None:
            return ""
        seen.append(p)
        if n < samples - 1:
            time.sleep(gap_s)
    mid = sorted(seen)[len(seen) // 2]
    if mid < BUSY_PCT:
        return ""
    own = {int(p) for p in own_pids}
    others = {pid: name for pid, name in apps().items() if pid not in own}
    if own and not others:
        return ""                                        # only our own programs are on the card: the load is ours
    names = ", ".join(sorted(set(others.values())))
    return (f"Another job is using the graphics card ({mid} % busy{': ' + names if names else ''}): "
            "renders are slower now, about 2× while it runs.")
