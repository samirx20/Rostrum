"""Running a call (OPERATIONS.md § 5): check every operation's targets and arguments, run each plan against the
document as the ones before it left it, then the app's whole-document check. Anything failing raises a
RostrumError naming the operation; the caller's document is untouched (we work on a copy)."""
from __future__ import annotations

import copy

from . import edits as E
from . import ids
from .conditions import describe, holds
from .errors import RostrumError, codes, did_you_mean
from .tree import fields, index


class Context:
    """What a plan gets: a read view of the working copy, and the four edits as calls."""

    def __init__(self, kind, work: dict, where: str):
        self.kind, self.doc, self.where, self.edits = kind, work, where, []

    def item(self, id_) -> dict:
        idx = index(self.doc, self.kind.lists)
        if id_ not in idx:
            raise RostrumError.not_found(self.where, "item", id_, idx)
        return idx[id_].item

    def _do(self, edit):
        self.edits.append(E.apply(self.doc, self.kind.lists, edit, self.where))

    def set(self, id_, path, value):
        path = [path] if isinstance(path, str) else list(path)
        self._do(E.Set(id_, path, value))

    def insert(self, parent, key, item, index=None):
        self._do(E.Insert(item["id"], parent, key, 10**9 if index is None else index, item))

    def remove(self, id_):
        self._do(E.Remove(id_))

    def move(self, id_, parent, key, index=None):
        self._do(E.Move(id_, (), (parent, key, 10**9 if index is None else index)))

    def new_id(self, type_) -> str:
        return ids.counted(index(self.doc, self.kind.lists), type_)

    def fail(self, code, subject, problem, accepted=(), hint=None):
        raise RostrumError(code, self.where, subject, problem, accepted, hint)


def normalize(calls) -> list[dict]:
    calls = [calls] if isinstance(calls, dict) else list(calls)
    out = []
    for n, c in enumerate(calls, 1):
        if not isinstance(c, dict) or "op" not in c:
            raise RostrumError(codes.BAD_ARGUMENT, f"call {n} of {len(calls)}", repr(c)[:60],
                               "is not an operation call", ['{"op": …, "target": [...], "args": {...}}'])
        target = c.get("target") or []
        out.append({"op": c["op"], "target": [target] if isinstance(target, str) else list(target),
                    "args": dict(c.get("args") or {})})
    return out


def _check_args(op, args, where):
    for name in args:
        if not op.param(name):
            names = [p.name for p in op.params]
            raise RostrumError(codes.BAD_ARGUMENT, where, f'"{name}"', f"is not an argument of {op.name}",
                               names, did_you_mean(name, names))
    for p in op.params:
        if p.required and p.name not in args:
            raise RostrumError(codes.BAD_ARGUMENT, where, f'"{p.name}"', "is required", [p.label])
    return {k: op.param(k).check(v, where) for k, v in args.items()}


def _check_targets(kind, op, targets, idx, where):
    items = []
    if op.targets is None:
        if targets:
            raise RostrumError(codes.BAD_ARGUMENT, where, f"target {targets}", f"{op.name} takes no target")
        return items
    if not targets:
        raise RostrumError(codes.BAD_ARGUMENT, where, "target []", f"{op.name} needs a {'/'.join(op.targets)}")
    for t in targets:
        if t not in idx:
            raise RostrumError.not_found(where, '/'.join(op.targets), t,
                                         [i for i, l in idx.items() if l.item.get("type") in op.targets])
        it = idx[t].item
        if it.get("type") not in op.targets:
            raise RostrumError(codes.BAD_ARGUMENT, where, f'target "{t}"', f"is a {it.get('type')}, not a "
                               f"{' or '.join(op.targets)}")
        if it.get("locked") and not op.name.endswith(".unlock"):
            raise RostrumError(codes.CHECK_FAILED, where, f'target "{t}"', "is locked", hint="Unlock it first.")
        if not holds(op.valid_when, fields(it, kind.lists), kind.facts(it)):
            raise RostrumError(codes.BAD_ARGUMENT, where, f'target "{t}"',
                               f"can't take {op.name} now: it needs {describe(op.valid_when)}")
        items.append(it)
    return items


def _check_valid_when(kind, op, items, args, where):
    """An argument that only applies sometimes must apply after this call (a value plus its switch is fine)."""
    for it in items or [{}]:
        values = {**fields(it, kind.lists), **args}
        facts = kind.facts(it) if it else {}
        for name in args:
            p = op.param(name)
            if not holds(p.valid_when, values, facts):
                raise RostrumError(codes.BAD_ARGUMENT, where, f'"{name}"',
                                   f"only applies when {describe(p.valid_when)}",
                                   hint=f"Set that in the same call to use {name}.")


def plan(kind, data: dict, calls) -> tuple[dict, list, list[dict]]:
    """(the new document, the applied edits, the normalized calls). Pure: `data` is not touched."""
    calls = normalize(calls)
    work, applied = copy.deepcopy(data), []
    for n, call in enumerate(calls, 1):
        where = f"op {n} of {len(calls)} ({call['op']})"
        op = kind.registry.get(call["op"], f"op {n} of {len(calls)}")
        items = _check_targets(kind, op, call["target"], index(work, kind.lists), where)
        args = _check_args(op, call["args"], where)
        _check_valid_when(kind, op, items, args, where)
        ctx = Context(kind, work, where)
        try:
            op.fn(ctx, call["target"], args)
        except RostrumError:
            raise
        except Exception as e:  # a bug in an operation is loud, never half-applied
            raise RostrumError(codes.INTERNAL, where, op.name, f"failed: {type(e).__name__}: {e}") from e
        call["args"] = args
        applied += ctx.edits
    problems = kind.check(work)
    if problems:
        raise RostrumError(codes.CHECK_FAILED, f"{len(calls)} op(s)", "the document", "would break its check: "
                           + "; ".join(problems))
    return work, applied, calls
