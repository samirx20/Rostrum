"""The command bar's list, fed by the operation registry: only what can run right now (absent, not greyed).

Each command is {"key", "label", "hint", "calls" | "select" | "do" | "reveal"}; running one applies its calls as ONE
operation batch, changes the selection (screen state), calls the app's own `do()` (an app action that isn't an
operation, e.g. Copy), or jumps to a setting that needs a value (`field_rows`). Everything acts on the WHOLE selection:
- The selection's settings (the ones every selected item shares, many.py) become one command per toggle ("Turn on
  Depth of field") and per choice option ("Type: Spot"), for params valid on every item; one call per item (mixed
  kinds have different field operations). Numbers, text and colours need a value: the settings panel.
- Other operations that fit every selected item (and enough of them: `min_targets`, e.g. a boolean needs two)
  target all of them; operations without a target too. They run directly when every required param has a default;
  a single required choice expands into one command per option ("Add layer: camera"). Anything else needs input
  the bar can't ask for yet, so it is left out.
- One "Select …" command per item not selected.
The hint names what a command acts on: the item, or `where` for several ("2 layers"; default "2 items").
Each command also carries the words search reads: `words` (its own: an operation's summary and fields, a field
command's own field), `context` (a field command's operation) and `weight` (importance: most used first).
"""
from __future__ import annotations

from rostrum_core.conditions import holds
from rostrum_core.params import IMPORTANCE

from . import many
from .match import starts


def field_words(p) -> str:
    """What a field answers to in search: its name, label, group and help (a colour also "color" and "colour")."""
    return f"{p.name} {p.label} {p.group} {p.help}" + (" color colour" if p.type == "color" else "")


def op_words(op) -> str:
    return f"{op.label} {op.name} {op.summary}"


def build(doc, selection: list[str], name_of, kind_of=None, where: str = "") -> list[dict]:
    """`kind_of(item)`: an item's kind in words (default: its type, capitalised); `where`: what the selection is
    called in hints (default: the one item's name, or "N items"). An operation on the whole document has no hint."""
    reg = doc.kind.registry
    where = where or (name_of(doc.item(selection[0])) if len(selection) == 1 else f"{len(selection)} items")
    out = _field_commands(doc, selection, where) if selection else []
    for op in reg.available(doc, selection):
        if op.fields:
            continue
        target = list(selection) if op.targets else None
        hint = where if target else ""     # no scope word for what is the whole document
        missing = [p for p in op.params if p.required and p.default is None]
        found = {"words": op_words(op) + " " + " ".join(field_words(p) for p in op.params),
                 "weight": IMPORTANCE.index(op.importance), "makes": makes(op.name)}
        if not missing:
            out.append({**_cmd(op.name, op.label, hint, [_call(op.name, target, {})]), **found})
        elif len(missing) == 1 and missing[0].type == "choice":
            p = missing[0]
            out += [{**_cmd(f"{op.name}:{o}", f"{op.label}: {p.option_label(o)}", hint, [_call(op.name, target, {p.name: o})]),
                     **found} for o in p.options]
    for it in doc.items():
        if it["id"] != doc.data["id"] and it["id"] not in selection:
            out.append({"key": "select:" + it["id"], "label": "Select " + name_of(it),
                        "hint": kind_of(it) if kind_of else it["type"].capitalize(),
                        "select": it["id"], "words": it["type"], "weight": len(IMPORTANCE)})
    return out


NEEDS_VALUE = ("number", "color", "text")


def field_rows(doc, item_id: str, label_of) -> list[dict]:
    """Ctrl+K's "Edit <setting>" for ONE selected item's settings that need a value (numbers, text, colours: `build`
    leaves them out), each valid now and on its settings row (not a script-only field). Running one jumps to the field
    (`reveal`: the bridge's revealField opens its group, scrolls the panel to it and puts the keys in it), so a word
    such as "velocity" or "volume" finds the setting. Search reads the field's own words (name, label, group, help)."""
    item = doc.item(item_id)
    facts = doc.kind.facts(item, doc)
    out = []
    for op in doc.kind.registry.available(doc, [item_id]):
        if op.fields and item["type"] in (op.targets or ()):
            out += [{"key": f"field:{p.name}", "label": f"Edit {p.label}", "reveal": p.name,
                     "hint": " · ".join(w for w in (label_of(item), p.group) if w),
                     "words": field_words(p), "context": op_words(op), "weight": IMPORTANCE.index(p.importance)}
                    for p in op.params if p.type in NEEDS_VALUE and p.shown != "script" and holds(p.valid_when, item, facts)]
    return out


def _field_commands(doc, selection, where):
    """Toggles and choices of the settings every selected item shares, valid on each; one call per item."""
    items = [doc.item(i) for i in selection]
    ops = [doc.kind.registry.field_op(it["type"]) for it in items]
    shared = many.shared_op(ops)
    if shared is None:
        return []
    facts = [doc.kind.facts(it, doc) for it in items]
    out = []
    for p in shared.params:
        if p.type not in ("toggle", "choice") or not all(holds(p.valid_when, it, f) for it, f in zip(items, facts)):
            continue
        now = [it.get(p.name, p.default) for it in items]
        sets = lambda v: [_call(op.name, [it["id"]], {p.name: v}) for op, it in zip(ops, items)]   # noqa: E731
        found = {"words": field_words(p), "context": op_words(ops[0]), "weight": IMPORTANCE.index(p.importance)}
        key = f"{ops[0].name}:{p.name}"
        if p.type == "toggle":
            on = not all(now)               # any off: turn all on; all on: turn all off
            out.append({**_cmd(key, f"{'Turn on' if on else 'Turn off'} {p.label}", where, sets(on)), **found})
        else:
            out += [{**_cmd(f"{key}={o}", f"{p.label}: {p.option_label(o)}", where, sets(o)), **found}
                    for o in p.options if any(v != o for v in now)]
    return out


def _call(op_name, target, args):
    call = {"op": op_name, "args": args}
    if target is not None:
        call["target"] = list(target)
    return call


def _cmd(key, label, hint, calls):
    return {"key": key, "label": label, "hint": hint, "calls": calls}


def makes(op_name: str) -> bool:
    """An operation that makes something new (track.add, comp.add, group.make): the command bar never runs one on a loose word."""
    return op_name.split(".")[-1].startswith(("add", "make", "new", "create"))


def search(commands: list[dict], query: str) -> list[dict]:
    """The commands whose words match the query, best first. The one rule: a command whose NAME is the query, or starts
    with it ("split" -> "Split at the playhead"), beats every other; then a name that has every query word starting a
    word of it ("move" finds "move it", never "remove"; any order, any case); then the command's own `words`, then
    the rest (hint, `context`, operation names). Within a rank: the app's own actions on the selection (`own`) first,
    then the most used (`weight`). A command that makes something new (`makes`) is found by its name only, never by a
    loose word of its summary ("mute" must not add a group). An empty query: every command, most used first."""
    q = " ".join(query.lower().split())
    words = q.split()
    ranked = sorted((r, 0 if c.get("own") else 1, c.get("weight", 0), i) for i, c in enumerate(commands)
                    if (r := rank(c, words, q)) is not None)
    return [commands[i] for *_, i in ranked]


def rank(c: dict, words: list[str], q: str = ""):
    """-2: the name is the query; -1: the name starts with it; 0: the name says it; 1: the name with the menu it sits in
    (`lead`: "Add effect" for "Add EQ") says it; 2: the command's own words say it; 3: anything else it carries says it;
    None: no match. A command that makes something new matches by name only (tiers -2 .. 1)."""
    label = c["label"].lower()
    if q and label == q:
        return -2
    if q and label.startswith(q):
        return -1
    own = f"{c['label']} {c.get('words', '')}"
    rest = f"{own} {c['hint']} {c.get('context', '')} {' '.join(k['op'] for k in c.get('calls', []))}"
    tiers = (c["label"], f"{c['label']} {c.get('lead', '')}", own, rest)
    r = next((r for r, text in enumerate(tiers) if starts(words, text.lower())), None)
    return None if r is not None and r > 1 and c.get("makes") else r
