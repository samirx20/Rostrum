"""The one list of operations. MCP's inspect_operations, the CLI help, the command bar and the inspector all
read it; there is no second list anywhere (OPERATIONS.md § 4).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from .conditions import check_refs, holds
from .errors import RostrumError, codes, did_you_mean
from .params import IMPORTANCE, Param

NAME = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
ITEM_KEYS = {"id", "type"}       # every item's own keys: never a field a person or agent sets


@dataclass
class Operation:
    name: str
    summary: str
    fn: Callable
    targets: tuple | None                 # item kinds it acts on; None = no target
    params: list[Param] = field(default_factory=list)
    label: str = ""
    importance: str = "primary"
    valid_when: dict | None = None        # on the target item's fields / facts
    fields: bool = False                  # its params ARE the target kind's fields (the inspector reads it)
    min_targets: int = 1                  # how many targets it needs at least (a boolean: 2); offered only then

    def param(self, name) -> Param | None:
        return next((p for p in self.params if p.name == name), None)

    def shown_targets(self) -> list | None:
        """The targets as an agent writes them: the song / document itself is the id "root", not its item type "doc"."""
        return [("root" if t == "doc" else t) for t in self.targets] if self.targets else None

    def schema(self) -> dict:
        props = {p.name: p.json_schema() for p in self.params}
        required = [p.name for p in self.params if p.required]
        return {"name": self.name, "summary": self.summary, "label": self.label,
                "target": self.shown_targets(),
                "arguments": {"type": "object", "properties": props, "required": required,
                              "additionalProperties": False},
                "params": [p.to_dict() for p in self.params],
                "importance": self.importance, "valid_when": self.valid_when, "fields": self.fields,
                "min_targets": self.min_targets}


@dataclass
class Alias:
    """A name another app or version writes for what this registry does under other names: `expand(call)` gives the
    calls to run instead (same target); `note` says, in words, what was run and why (it goes in the reply)."""
    name: str
    expand: Callable
    note: str | None = None


class Registry:
    def __init__(self):
        self._ops: dict[str, Operation] = {}
        self._aliases: dict[str, Alias] = {}

    def operation(self, name, summary, target=None, params=(), label="", importance="primary",
                  valid_when=None, fields=False, min_targets=1):
        """Decorator: @reg.operation("camera.set", "Change a camera.", target="camera", params=[...])."""
        def register(fn):
            self.add(Operation(name, summary, fn, _kinds(target), list(params), label or name, importance,
                               valid_when, fields, min_targets))
            return fn
        return register

    def add(self, op: Operation):
        problems = []
        if not NAME.match(op.name):
            problems.append("name must be area.verb, lower case")
        if op.name in self._ops:
            problems.append("is already registered")
        if op.importance not in IMPORTANCE:
            problems.append(f"importance {op.importance!r}")
        names = [p.name for p in op.params]
        if len(set(names)) != len(names):
            problems.append("has two params with the same name")
        if op.fields and ITEM_KEYS & set(names):
            problems.append(f"field params can't be named {sorted(ITEM_KEYS & set(names))} (item keys)")
        if op.fields:   # a field op's conditions read its own params; others may read the target's fields
            for p in op.params:
                problems += [f"{p.name}: {x}" for x in check_refs(p.valid_when, names)]
        if op.fields and (not op.targets or any(self.field_op(k) for k in op.targets)):
            problems.append("fields=True needs a target kind that has no field op yet")
        if problems:
            raise ValueError(f"operation {op.name}: " + "; ".join(problems))
        self._ops[op.name] = op

    def alias(self, name, to=None, note=None, expand=None):
        """Read `name` as another operation: `to` (same target and arguments), or whatever `expand(call)` returns (a list
        of calls). Said in the reply when `note` is given. A real operation of the same name wins (never shadowed)."""
        if name in self._ops or name in self._aliases or not NAME.match(name):
            raise ValueError(f"alias {name}: must be area.verb and not already an operation or alias")
        self._aliases[name] = Alias(name, expand or (lambda call: [{**call, "op": to}]), note)

    def resolve(self, calls) -> list[dict]:
        """`calls` with every alias written as the operations it stands for (the history records those)."""
        out = []
        for c in calls:
            a = self._aliases.get(c["op"]) if c["op"] not in self._ops else None
            out += [{**x, "said": c["op"]} for x in a.expand(c)] if a else [c]   # "said": the name the caller wrote
        return out

    def alias_notes(self, calls) -> list[str]:
        """What to tell the caller about the aliases it used (once each)."""
        used = dict.fromkeys(c["op"] for c in calls if c["op"] not in self._ops and c["op"] in self._aliases)
        return [self._aliases[n].note for n in used if self._aliases[n].note]

    def ops(self) -> list[Operation]:
        return list(self._ops.values())

    def get(self, name, where="") -> Operation:
        if name not in self._ops:
            raise RostrumError(codes.UNKNOWN_OPERATION, where, f'"{name}"', "is not an operation in this app",
                               sorted(self._ops), did_you_mean(name, self._ops))
        return self._ops[name]

    def field_op(self, kind) -> Operation | None:
        return next((o for o in self._ops.values() if o.fields and o.targets and kind in o.targets), None)

    def available(self, doc, target_ids=()) -> list[Operation]:
        """Operations that can run right now: those that fit these targets (every one of them, and enough of them),
        plus those that need no target (Add layer). The command bar's list (absent, not greyed)."""
        items = [doc.item(i) for i in target_ids]
        out = []
        for op in self._ops.values():
            if op.targets is None:
                out.append(op)
                continue
            if len(items) >= max(1, op.min_targets) and all(it["type"] in op.targets and holds(op.valid_when, it, doc.kind.facts(it, doc))
                             for it in items):
                out.append(op)
        return out


def _kinds(target):
    if target is None:
        return None
    return (target,) if isinstance(target, str) else tuple(target)
