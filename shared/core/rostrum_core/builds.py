"""Which build of a program to run, when the same program was built more than once (target/release/, target/agent/ ...).

The newest file wins, never a fixed order: a leftover build from last week must not beat the one just made. When more
than one exists and they differ, one line on stderr says which was used and which were passed over (once per choice).

    builds.newest([release_exe, agent_exe], "the Sound engine")     # the newest that exists, else None
"""
from __future__ import annotations

import sys
from pathlib import Path

_said: set = set()


def newest(candidates, what: str) -> Path | None:
    found = [Path(p) for p in candidates if Path(p).is_file()]
    if not found:
        return None
    best = max(found, key=lambda p: p.stat().st_mtime)
    stamp = lambda p: (p.stat().st_size, p.stat().st_mtime)
    others = [p for p in found if p != best and stamp(p) != stamp(best)]
    key = (what, str(best), tuple(map(str, others)))
    if others and key not in _said:
        _said.add(key)
        print(f"{what}: using the newest build, {best}; older ones passed over: {', '.join(map(str, others))}",
              file=sys.stderr)
    return best
