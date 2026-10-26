"""What a script run reports: what was held back, what it took out, in plain words (see merge.py)."""
from __future__ import annotations

from dataclasses import dataclass, field


SHOWN = 5   # names a reply lists before saying "and N more"
GONE = "(its place is gone)"   # a held edit that could not land at all (its parent is gone, its id is taken)


def _owner(r: dict) -> str:
    """Who an item belongs to: a key's id is `owner.field.k1500`, so its owner is the first part; any other item is its own."""
    return r["id"].split(".")[0] if r.get("type") == "key" else r["id"]


def _span(names: list) -> str:
    return names[0] if len(names) == 1 else f"{names[0]}–{names[-1]}" if len(names) > 2 else " and ".join(names)


def removed_text(removed: list) -> str:
    """What a run took out, in a line: counts per kind with the layers they were on ("98 keys on pollen0–pollen55"), then
    the first few ids. The full list is `data.removed` when asked for (`detail`)."""
    kinds: dict[str, list] = {}
    for r in removed:
        kinds.setdefault(r["type"], []).append(r)
    parts = []
    for kind, items in kinds.items():
        owners = list(dict.fromkeys(_owner(r) for r in items))
        on = "" if kind != "key" else f" on {_span(owners)}"
        parts.append(f"{len(items)} {kind}{'s' * (len(items) != 1)}{on}")
    first = ", ".join(r["id"] for r in removed[:SHOWN])
    more = f" and {len(removed) - SHOWN} more" if len(removed) > SHOWN else ""
    return f"{', '.join(parts)} (first: {first}{more})"


_WANTS = {"(add)": "add it", "(remove)": "remove it", "(move)": "move it"}


def held_words(h: dict) -> str:
    """One held-back thing in words: placeholders like "(add)" / "(kept, edited)" say who got there first instead."""
    name = h["who"] if h["who"] not in ("?", None) else "someone else (a person or agent; the history doesn't say who, e.g. the change was made inside it or before the file was opened)"
    who = f'{name} ("{h["label"]}")' if h["label"] not in ("?", None) else name
    if h["kept"] == GONE:                   # not someone's work: the edit can't land (force can't help either)
        return (f'{h["key"]}: the script could not {_WANTS.get(h["script"], "set it").replace(" it", "")} it: {h["label"]} '
                "(force can't help: remove or rename what is in its way, or give the script's item another id)")
    if h["script"] in _WANTS:
        return f'{h["key"]}: the script wanted to {_WANTS[h["script"]]}, but it was already changed by {who}'
    if h["kept"] == "(kept, edited)":
        return f'{h["key"]}: script says {h["script"]!r}, but it was already added or edited by {who}'
    return f'{h["key"]}: script says {h["script"]!r}, kept {h["kept"]!r} ({who})'


@dataclass
class MergeReport:
    script: str
    change: object = None                       # the Change, or None when nothing new applied
    applied: int = 0
    held: list = field(default_factory=list)    # {"key", "script", "kept", "who", "label"}
    removed: list = field(default_factory=list) # {"id", "type"}: the items the run took out (topmost ones)
    others: list = field(default_factory=list)  # first run under this name: the names of the scripts that already made things
    broken: list = field(default_factory=list)  # check failures the document had before this run (not this run's)

    def warnings(self) -> list:
        """One line per thing a caller must not miss: each held-back value, what the run took out, and that a new
        script name adds beside what earlier scripts made instead of replacing it."""
        held = [f'Held back {held_words(h)}.' + ("" if h["kept"] == GONE else f' Pass force: ["{h["key"]}"] to take over.')
                for h in self.held]
        gone = [f"Removed {removed_text(self.removed)}: the script no longer makes them."] if self.removed else []
        new = [f'"{self.script}" is a new script name, so it ADDED its items beside what {", ".join(self.others)} made. '
               f"To change those instead, run again under their name (a script re-run under the same name replaces what it made)."] if self.others else []
        old = [f"The document was already broken before this run (not by it): {p}." for p in self.broken]
        return held + gone + new + old

    def summary(self) -> str:
        text = f"Script {self.script}: {self.applied} change(s) applied"
        if self.removed:
            text += f"; removed {removed_text(self.removed)}"
        if not self.held:
            return text + "."
        lines = [f"  {held_words(h)}" for h in self.held]
        keys = ", ".join(f'"{h["key"]}"' for h in self.held if h["kept"] != GONE)
        win = (f"\nTo let the script win, run again with force: [{keys}] (or force: true for all); or change them with an "
               "operation." if keys else "")
        return text + f", {len(self.held)} held back:\n" + "\n".join(lines) + win
