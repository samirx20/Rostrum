"""Short findings lists, app-neutral: names made in a loop share a stem, a few examples then "…", and the cap with the
sentence on how to ask for the rest. Each app's look_motion groups its own kinds with these."""
from __future__ import annotations

import re

LIMIT = 20          # lines of each kind (items, findings) a reply lists before "N more"


def stem(name: str) -> str:
    """mote_12 -> mote_# : names made in a loop share one."""
    return re.sub(r"\d+", "#", name)


def examples(ids: list[str], n: int = 3) -> str:
    return ", ".join(ids[:n]) + (" …" if len(ids) > n else "")


def capped(groups: list[dict], limit: int, ask: str) -> tuple[list[dict], str]:
    """The first `limit` groups and the sentence about the rest ("" when none left out); `ask` says how to see them."""
    if len(groups) <= limit:
        return groups, ""
    left = groups[limit:]
    items = sum(g.get("count", 1) for g in left)
    return groups[:limit], f"{len(left)} more finding line{'s' * (len(left) != 1)} ({items} findings) not listed: {ask}"
