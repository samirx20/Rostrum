"""Stable ids (OPERATIONS.md § 2): written ids win, scripts count per type, timeline things from content,
the GUI uses random ones. An id never changes once given."""
from __future__ import annotations

import re
import secrets


def counted(taken, type_: str, reserved=()) -> str:
    """The next `type_N` not taken and not reserved (every quoted word in a script is reserved)."""
    taken = set(taken) | set(reserved)
    n = 1
    while f"{type_}_{n}" in taken:
        n += 1
    return f"{type_}_{n}"


def from_content(parent: str, kind: str, ms: int | float) -> str:
    """`chords.n1500`-style: from the parent and where the thing sits, so inserting earlier shifts nothing."""
    return f"{parent}.{kind}{int(round(ms))}"


def random_id(prefix: str = "id") -> str:
    return f"{prefix}_{secrets.token_hex(4)}"


VALID = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]*$")


def is_valid(id_: str) -> bool:
    return isinstance(id_, str) and bool(VALID.match(id_))
