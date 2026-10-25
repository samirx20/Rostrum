"""One place that asks "is this file there, and has it changed?", so a screen can keep that off the edit path.

Programs that run once (an export, an agent's script) ask the disk every time: `stamp(path)` is one stat. A screen
calls `watching()` once and `tick()` on its own timer (about once a second): from then on an answer is kept until the
next tick, or until this process wrote the file (`forget`). A document change on the screen then asks the disk nothing
for these lookups. `is_file` (used where a missing file is an error) never trusts "not there": it looks again, so a
file put back shows at once.
"""
from __future__ import annotations

from pathlib import Path

_kept: dict = {}        # str(path) -> stamp (st_mtime_ns, st_size), or None for a file that was not there
_on = [0]               # screens that tick; 0 = nobody does, every ask goes to the disk


def watching():
    """A screen takes over the ticking; call the returned function when it closes (a second call does nothing)."""
    _on[0] += 1
    live = [True]

    def stop():
        if live[0]:
            live[0] = False
            _on[0] -= 1
            if not _on[0]:
                _kept.clear()
    return stop


def tick() -> None:
    """The screen's timer: what the files showed may be old now."""
    _kept.clear()


def forget(path) -> None:
    """This process wrote `path`: its kept answer is old."""
    _kept.pop(str(path), None)


def stamp(path, fresh: bool = False) -> tuple[int, int] | None:
    """(modified, size) of the file, or None when it is not there. `fresh`: look at the disk now."""
    key = str(path)
    if _on[0] and not fresh and key in _kept:
        return _kept[key]
    try:
        st = Path(path).stat()
        got = (st.st_mtime_ns, st.st_size)
    except OSError:
        got = None
    if _on[0]:
        _kept[key] = got
    return got


def is_file(path) -> bool:
    """True when the file is there. A kept "there" is trusted until the next tick; "not there" is looked at again."""
    return stamp(path) is not None or stamp(path, fresh=True) is not None
