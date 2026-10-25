"""Stable ids (OPERATIONS.md § 2): written ids win, scripts count per type, timeline things from content,
the GUI uses random ones. An id never changes once given."""
from __future__ import annotations

import re
import secrets


def counted(taken, type_: str, reserved=(), sep: str = "_", start: int = 1) -> str:
    """The next `type_N` not taken and not reserved (every quoted word in a script is reserved). The one source
    of counted ids, for items (`layer_2`) and for change groups (`agent-run-2`, `sep="-"`). `start`: an N known to be
    no higher than the answer (a caller that only adds ids resumes after its last one: 10,000 strokes stay linear)."""
    taken, reserved = (s if isinstance(s, (set, frozenset, dict)) else set(s) for s in (taken, reserved))
    n = start
    while f"{type_}{sep}{n}" in taken or f"{type_}{sep}{n}" in reserved:
        n += 1
    return f"{type_}{sep}{n}"


def from_content(parent: str, kind: str, ms: int | float) -> str:
    """`chords.n1500`-style: from the parent and where the thing sits, so inserting earlier shifts nothing."""
    return f"{parent}.{kind}{int(round(ms))}"


def random_id(prefix: str = "id") -> str:
    return f"{prefix}_{secrets.token_hex(4)}"


VALID = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]*$")


def is_valid(id_: str) -> bool:
    return isinstance(id_, str) and bool(VALID.match(id_))
