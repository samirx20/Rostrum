"""A field a script gives where it does nothing is never dropped in silence (no gates: the script runs as written).

- A field that applies only while an on/off switch of the same item is set (glow `color` while Layer's own colour is
  off, a stroke colour while Stroke is on, an image's exposure while Adjust is on …) turns that switch the way it needs
  when the script gives the field and not the switch: `effect("glow", color=WARM)` glows WARM. A switch the script
  gives itself is kept as written.
- Any other field given (a value or keys) that does nothing there is named in run_script's reply (`notes`), with what
  it needs and what to write instead: a layout place (`shiftY`, `grow`, `margin` …) on a layer not in a row, column or
  grid, a field whose switch the script itself set the other way (`color` with `ownColor=True`) …
- Only the script's own lines count: the blocks made for it (button, card, device …) keep their own settings.
"""
from __future__ import annotations

import sys

from rostrum_core.conditions import describe, holds, refs

from . import fields as F

INSTEAD = {"shiftX": "key x to move it", "shiftY": "key y to move it"}   # what does the move outside a layout
FACTS = ("inLayout",)       # the facts worked out here; a condition on any other fact is left to the screen
OFF = (0, "", "none")       # a value that asks for nothing (False too)
SHOWN = 6                   # items named per field


def _switch(cond):
    """(switch, value) when `cond` is one on/off field of the item being so; else None."""
    if cond and "is" in cond and isinstance(cond["is"][1], bool):
        return cond["is"][0], cond["is"][1]
    return None


def _by_author(build) -> bool:
    """The call came straight from the script's own lines, not from a block made for it (a button's outline colour
    with its outline off is the block's own setting): the first frame outside the script words (script.py, and the
    row / column / group words of script_layout.py) is the script."""
    from . import script, script_layout
    f = sys._getframe(2)
    while f is not None and f.f_code.co_filename in (script.__file__, script_layout.__file__, __file__):
        f = f.f_back
    return f is not None and f.f_code.co_filename == getattr(build, "name", None)


def given(build, node: dict, names) -> None:
    """The script's own lines gave `names` on `node` (values or keys): remember them and turn the switches they need."""
    if not _by_author(build):
        return
    mine = build.given.setdefault(node["id"], (node, set()))[1]
    mine.update(names)
    for name in names:
        p = F.param(node["type"], name)
        sw = _switch(p.valid_when) if p is not None else None
        if sw and sw[0] not in mine and F.param(node["type"], sw[0]) is not None:
            node[sw[0]] = sw[1]


def _parents(node: dict, parent, out: dict) -> None:
    for v in node.values():
        if isinstance(v, list):
            for c in v:
                if isinstance(c, dict) and "id" in c:
                    out[c["id"]] = node
                    _parents(c, node, out)


def notes(build) -> list[str]:
    """One line per field given where it does nothing, naming the items (run_script shows them in its reply); first,
    the lines saying how a common form was read (a CSS margin list, dash=[8, 8] …: script_layout.say)."""
    up: dict = {}
    _parents(build.root, None, up)
    found: dict[tuple, list[str]] = {}
    for nid, (node, names) in build.given.items():
        if node["type"] not in F.FIELDS:
            continue
        parent = up.get(nid)
        facts = {"inLayout": bool(parent) and parent.get("type") == "group" and parent.get("layout", "none") != "none"}
        values = {**F.defaults(node["type"]), **node}
        keyed = {k.get("prop") for k in node.get("keys", [])}
        for name in sorted(names):
            p = F.param(node["type"], name)
            v = values.get(name)
            if p is None or (name not in keyed and (v == p.default or v is False or v in OFF)):
                continue                                    # its default, or off (hugPin=False): nothing is lost
            if name in ("sizeW", "sizeH") and v == "fixed":
                continue                                    # w= / h= as given: a group's own size (a section's box) applies anywhere
            cond, reads = p.valid_when, refs(p.valid_when)
            if cond is None or any(kind == "fact" and f not in FACTS for kind, f in reads):
                continue
            if not holds(cond, values, facts):
                found.setdefault((node["type"], name, describe(cond, {q.name: q.label for q in F.FIELDS[node["type"]]})), []).append(nid)
    out = []
    for (kind, name, needs), ids in found.items():
        who = ", ".join(ids[:SHOWN]) + (f" and {len(ids) - SHOWN} more" if len(ids) > SHOWN else "")
        tail = f"; {INSTEAD[name]}" if name in INSTEAD else ""
        out.append(f"{name} on {who} does nothing there: a {kind}'s {name} applies only when {needs}{tail}.")
    return list(getattr(build, "said", [])) + out
