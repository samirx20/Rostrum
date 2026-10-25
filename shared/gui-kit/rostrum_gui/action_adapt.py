"""Turn an app's older action dicts into kit `Action`s (actions.py), so an app's data moves over unchanged.

The dict shape (Sound's `screensound/actions.py`; the older "bar" / "menu" names are read too):
    key | id            "sel:mute" (a leading "sel:" is dropped: the id is "mute")
    label               words, or a function of the selection
    shortcut            "Ctrl+G": becomes the kit `job` when the key map says it is a SHARED key (so the key follows
                        the shared map), else the app's own `keys` (it must be in the app's key map)
    valid_when | valid  valid(facts) -> bool
    importance          "primary" | "bar" -> on the context bar; "bar2" -> on the bar, after the rest;
                        "secondary" | "menu" -> under ⋯ and in menus
    promoted_when | promoted
    group               a divider group ("edit" = the edit block)
    menu | bar          the bar button the action sits under ("Transpose")
    calls, do           kept as they are (calls(facts) -> operation calls; do = an app's own action)
    needs | why         the sentence for a key pressed when it doesn't apply
    amounts, asks, fit  the amounts popover's (actions.Action): parameter names, "asks first", the app's say on rows
min_targets: give it in the dict (Layer as one sound: 2) so the kit's one guard holds it; without it the action's
own `valid` decides alone (0).
A shortcut that is neither a shared key nor one of the app's own keys is refused at start-up, naming the action.
"""
from __future__ import annotations

from .actions import Action
from .keymap import KeyMap, normal

PRIMARY = {"primary": 100, "bar": 100, "bar2": 200}
SECONDARY = ("secondary", "menu")


def one(d: dict, keymap: KeyMap, rank: int = 100) -> Action:
    id_ = (d.get("id") or d["key"]).removeprefix("sel:")
    imp = d.get("importance", "secondary")
    if imp not in PRIMARY and imp not in SECONDARY:
        raise ValueError(f"action {id_}: importance {imp!r} is not one of {', '.join([*PRIMARY, *SECONDARY])}")
    job = keys = ""
    short = d.get("shortcut") or d.get("keys") or ""
    if short:
        where = keymap.where(short)
        if where == "shared":
            job = keymap.job_of(short)
        elif where == keymap.app:
            keys = normal(short)
        else:
            raise ValueError(f'action {id_}: its key {normal(short)} is neither a shared key nor one of '
                             f"{keymap.app}'s own keys. Add it to {keymap.app}'s key map, or pick a shared key.")
    return Action(
        id=id_, label=d.get("label", ""), valid=d.get("valid_when") or d.get("valid"), min_targets=d.get("min_targets", 0),
        importance="primary" if imp in PRIMARY else "secondary", rank=PRIMARY.get(imp, rank),
        promoted=d.get("promoted_when") or d.get("promoted"), job=job, keys=keys, group=d.get("group", ""),
        bar=d.get("menu") or d.get("bar") or "", calls=d.get("calls"), do=d.get("do", ""),
        why=d.get("needs") or d.get("why") or "", amounts=tuple(d.get("amounts") or ()), asks=bool(d.get("asks")),
        fit=d.get("fit"))


def from_dicts(dicts, keymap: KeyMap) -> list[Action]:
    """Every dict as an Action, in order. Two dicts may share a key (Mute / Unmute): the job's valid one runs."""
    return [one(d, keymap) for d in dicts]
