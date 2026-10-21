"""The command bar's list, fed by the operation registry: only what can run right now (absent, not greyed).

Each command is {"key", "label", "hint", "calls" | "select"}; running one applies its calls as ONE operation
batch (or changes the selection, which is screen state, not a document change).
- The selected item's field operation becomes one command per toggle ("Turn on Depth of field") and per other
  choice option ("Type: Spot"), for params valid right now. Numbers, text and colours need a value: inspector.
- Other operations on the selection, and operations without a target, run directly when every required param
  has a default; a single required choice expands into one command per option ("Add layer: camera").
  Anything else needs input the bar can't ask for yet, so it is left out.
- One "Select …" command per item.
"""
from __future__ import annotations

from rostrum_core.conditions import holds


def build(doc, selection: list[str], name_of) -> list[dict]:
    reg = doc.kind.registry
    ops = reg.available(doc, selection)
    out: list[dict] = []
    where = name_of(doc.item(selection[0])) if len(selection) == 1 else f"{len(selection)} items"
    for op in ops:
        target = list(selection) if op.targets else None
        hint = where if target else "Document"
        if op.fields:
            out += _field_commands(doc, op, selection, name_of)
            continue
        missing = [p for p in op.params if p.required and p.default is None]
        if not missing:
            out.append(_cmd(op.name, op.label, hint, op.name, target, {}))
        elif len(missing) == 1 and missing[0].type == "choice":
            p = missing[0]
            out += [_cmd(f"{op.name}:{o}", f"{op.label}: {o}", hint, op.name, target, {p.name: o})
                    for o in p.options]
    for it in doc.items():
        if it["id"] != doc.data["id"] and it["id"] not in selection:
            out.append({"key": "select:" + it["id"], "label": "Select " + name_of(it), "hint": it["type"].capitalize(),
                        "select": it["id"]})
    return out


def _field_commands(doc, op, selection, name_of):
    if len(selection) != 1:
        return []
    item = doc.item(selection[0])
    facts = doc.kind.facts(item)
    out = []
    for p in op.params:
        if not holds(p.valid_when, item, facts):
            continue
        now = item.get(p.name, p.default)
        if p.type == "toggle":
            word = "Turn off" if now else "Turn on"
            out.append(_cmd(f"{op.name}:{p.name}", f"{word} {p.label}", name_of(item), op.name, selection,
                            {p.name: not now}))
        elif p.type == "choice":
            out += [_cmd(f"{op.name}:{p.name}={o}", f"{p.label}: {o}", name_of(item), op.name, selection, {p.name: o})
                    for o in p.options if o != now]
    return out


def _cmd(key, label, hint, op_name, target, args):
    call = {"op": op_name, "args": args}
    if target is not None:
        call["target"] = list(target)
    return {"key": key, "label": label, "hint": hint, "calls": [call]}


def search(commands: list[dict], query: str) -> list[dict]:
    """Every word of the query appears in the label, the hint or the operation name (any order, any case)."""
    words = query.lower().split()
    def text(c):
        names = " ".join(call["op"] for call in c.get("calls", []))
        return f"{c['label']} {c['hint']} {names}".lower()
    return [c for c in commands if all(w in text(c) for w in words)]
