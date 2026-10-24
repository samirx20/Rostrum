"""When a control or operation is valid: the whole condition language (from S3 proofs/gui-mock/controls.json).

    {"is": [name, value]}   the field `name` of the target equals value
    {"not": c}  {"all": [c, ...]}  {"any": [c, ...]}
    {"fact": name}          a fact the document kind reports about the item (e.g. a clip has audio)
    "say": [yes, no]        on any of these: its plain words when it holds / when it does not (refusals use them
                            instead of spelling the parts out)
    None                    always valid
"""
from __future__ import annotations

import re


def holds(cond, values: dict, facts: dict | None = None) -> bool:
    if cond is None:
        return True
    facts = facts or {}
    if "is" in cond:
        name, want = cond["is"]
        return values.get(name) == want
    if "not" in cond:
        return not holds(cond["not"], values, facts)
    if "all" in cond:
        return all(holds(c, values, facts) for c in cond["all"])
    if "any" in cond:
        return any(holds(c, values, facts) for c in cond["any"])
    if "fact" in cond:
        return bool(facts.get(cond["fact"], False))
    raise ValueError(f"unknown condition {cond!r}")


def refs(cond) -> list[tuple[str, str]]:
    """[("param", name) | ("fact", name)]: what a condition reads, for checking registrations."""
    if not cond:
        return []
    if "is" in cond:
        return [("param", cond["is"][0])]
    if "not" in cond:
        return refs(cond["not"])
    if "fact" in cond:
        return [("fact", cond["fact"])]
    if "all" in cond or "any" in cond:
        return [r for c in cond.get("all", cond.get("any")) for r in refs(c)]
    raise ValueError(f"unknown condition {cond!r}")


def check_refs(cond, names) -> list[str]:
    """Problems with a condition: unknown keys or fields it names that don't exist."""
    try:
        return [f"valid_when names unknown field {n!r}" for k, n in refs(cond) if k == "param" and n not in names]
    except ValueError as e:
        return [str(e)]


# Facts the document kinds report, in plain words: (what it takes for the fact to hold, what it takes for it not to).
# The one table every app's refusals read; a fact missing here falls back to its own name spelled out in words.
FACTS = {
    "animated": ("it has keys (or something inside it has)", "it has no keys"),
    "animating": ("you are animating", "you are not animating"),
    "any_locked": ("a picked item is locked", "no picked item is locked"),
    "any_pinned": ("a picked layer is pinned to the frame", "no picked layer is pinned to the frame"),
    "any_unpinned": ("a picked layer is not pinned to the frame", "every picked layer is pinned to the frame"),
    "articulated": ("its sound set has playing styles", "its sound set has no playing styles"),
    "bendLane": ("it has a pitch-bend lane", "it has no pitch-bend lane"),
    "bendable": ("it can bend", "it can't bend"),
    "boned": ("it has bones", "it has no bones"),
    "color": ("the key is a colour", "the key is not a colour"),
    "fontItalic": ("its font has an italic", "its font has no italic"),
    "frameAway": ("the frame is away from home", "the frame is at home"),
    "hasPaint": ("it holds paint", "it holds no paint"),
    "has_frame": ("the scene has a frame", "the scene has no frame"),
    "inLayout": ("it sits in a group that arranges its layers", "it is not in a group that arranges its layers"),
    "number": ("the key is a number", "the key is not a number"),
    "painted": ("it holds paint", "it holds no paint"),
    "plucked": ("its sound is plucked", "its sound is not plucked"),
    "rawSpring": ("the spring is set by its raw numbers", "the spring is set by bounce and speed"),
    "same_list": ("the picked items are in one list", "the picked items are in different lists"),
    "shape": ("the key is a shape", "the key is not a shape"),
    "struck": ("its sound is struck", "its sound is not struck"),
    "underCamera": ("it sits directly in a scene (not in a group)", "it sits in a group, not directly in a scene"),
    "vibratoLane": ("it has a vibrato lane", "it has no vibrato lane"),
}


def spelled(name: str) -> str:
    """A field or fact name as words: 'boxWidth' -> 'box width', 'any_locked' -> 'any locked'."""
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name).replace("_", " ").lower()


def _fact(name: str, holding: bool) -> str:
    yes_no = FACTS.get(name)
    return yes_no[0 if holding else 1] if yes_no else f"{spelled(name)}{'' if holding else ' is not so'}"


def _value(v) -> str:
    return {True: "on", False: "off"}.get(v, f"{v}" if isinstance(v, (int, float)) else f"“{v}”")


def describe(cond, labels: dict | None = None, holding: bool = True) -> str:
    """Plain words for a refusal: 'Depth is on', 'it sits directly in a scene and Locked is off'. `labels`: field name ->
    the label people see (an operation's params); a field without one is its name spelled out. `holding` False: the
    words for the condition NOT holding (what `not` asks)."""
    labels = labels or {}
    if cond is None:
        return "always"
    if "say" in cond:
        return cond["say"][0 if holding else 1]
    if "is" in cond:
        name, want = cond["is"]
        label = labels.get(name) or spelled(name).capitalize()
        if isinstance(want, bool):
            return f"{label} is {_value(want if holding else not want)}"
        return f"{label} is {'' if holding else 'not '}{_value(want)}"
    if "not" in cond:
        return describe(cond["not"], labels, not holding)
    if "fact" in cond:
        return _fact(cond["fact"], holding)
    parts = [describe(c, labels, holding) for c in cond.get("all", cond.get("any", []))]
    all_of = "all" in cond
    return (" and " if all_of == holding else " or ").join(parts)
