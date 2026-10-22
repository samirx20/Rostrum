"""The command bar's list, fed by the operation registry: only what can run right now (absent, not greyed).

Each command is {"key", "label", "hint", "calls" | "select"}; running one applies its calls as ONE operation
batch (or changes the selection, which is screen state, not a document change).
- The selected item's field operation becomes one command per toggle ("Turn on Depth of field") and per other
  choice option ("Type: Spot"), for params valid right now. Numbers, text and colours need a value: inspector.
- Other operations on the selection, and operations without a target, run directly when every required param
  has a default; a single required choice expands into one command per option ("Add layer: camera").
  Anything else needs input the bar can't ask for yet, so it is left out.
- One "Select …" command per item.
Each command also carries the words search reads: `words` (its own: an operation's summary and fields, a field
command's own field), `context` (a field command's operation) and `weight` (importance: most used first).
"""
from __future__ import annotations

import re

from rostrum_core.conditions import holds
from rostrum_core.params import IMPORTANCE


def field_words(p) -> str:
    """What a field answers to in search: its name, label, group and help (a colour also "color" and "colour")."""
    return f"{p.name} {p.label} {p.group} {p.help}" + (" color colour" if p.type == "color" else "")


def op_words(op) -> str:
    return f"{op.label} {op.name} {op.summary}"


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
        found = {"words": op_words(op) + " " + " ".join(field_words(p) for p in op.params),
                 "weight": IMPORTANCE.index(op.importance)}
        if not missing:
            out.append({**_cmd(op.name, op.label, hint, op.name, target, {}), **found})
        elif len(missing) == 1 and missing[0].type == "choice":
            p = missing[0]
            out += [{**_cmd(f"{op.name}:{o}", f"{op.label}: {p.option_label(o)}", hint, op.name, target, {p.name: o}), **found}
                    for o in p.options]
    for it in doc.items():
        if it["id"] != doc.data["id"] and it["id"] not in selection:
            out.append({"key": "select:" + it["id"], "label": "Select " + name_of(it), "hint": it["type"].capitalize(),
                        "select": it["id"], "words": it["type"], "weight": len(IMPORTANCE)})
    return out


def _field_commands(doc, op, selection, name_of):
    if len(selection) != 1:
        return []
    item = doc.item(selection[0])
    facts = doc.kind.facts(item, doc)
    out = []
    for p in op.params:
        if not holds(p.valid_when, item, facts):
            continue
        now = item.get(p.name, p.default)
        found = {"words": field_words(p), "context": op_words(op), "weight": IMPORTANCE.index(p.importance)}
        if p.type == "toggle":
            word = "Turn off" if now else "Turn on"
            out.append({**_cmd(f"{op.name}:{p.name}", f"{word} {p.label}", name_of(item), op.name, selection,
                               {p.name: not now}), **found})
        elif p.type == "choice":
            out += [{**_cmd(f"{op.name}:{p.name}={o}", f"{p.label}: {p.option_label(o)}", name_of(item), op.name, selection,
                            {p.name: o}), **found}
                    for o in p.options if o != now]
    return out


def _cmd(key, label, hint, op_name, target, args):
    call = {"op": op_name, "args": args}
    if target is not None:
        call["target"] = list(target)
    return {"key": key, "label": label, "hint": hint, "calls": [call]}


def search(commands: list[dict], query: str) -> list[dict]:
    """The commands whose words match the query, best first: every query word starts a word ("move" finds "move it",
    never "remove"; any order, any case). The label saying it ranks first, then the command's own `words`, then the
    rest (hint, `context`, operation names); within a rank the most used (`weight`) first. An empty query: every
    command, most used first."""
    words = query.lower().split()
    ranked = sorted((r, c.get("weight", 0), i) for i, c in enumerate(commands) if (r := rank(c, words)) is not None)
    return [commands[i] for _, _, i in ranked]


def rank(c: dict, words: list[str]):
    """0: the label says it; 1: the command's own words say it; 2: anything else it carries says it; None: no match."""
    own = f"{c['label']} {c.get('words', '')}"
    rest = f"{own} {c['hint']} {c.get('context', '')} {' '.join(k['op'] for k in c.get('calls', []))}"
    return next((r for r, text in enumerate((c["label"], own, rest)) if starts(words, text.lower())), None)


def starts(words: list[str], text: str) -> bool:
    """Every word (lower case) starts a word of the text: the one word match for commands and settings alike."""
    return all(re.search(r"(?<![a-z0-9])" + re.escape(w), text) for w in words)
