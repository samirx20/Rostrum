"""Running a call (OPERATIONS.md § 5): check every operation's targets and arguments, run each plan against the
document as the ones before it left it, then the app's whole-document check. Anything failing raises a
RostrumError naming the operation; the caller's document is untouched (we work on a fork: edits.fork)."""
from __future__ import annotations

from . import bug
from . import edits as E
from . import ids, locks
from .conditions import describe, holds
from .errors import RostrumError, codes, did_you_mean
from .tree import View, fields, index, subtree_ids


class Context:
    """What a plan gets: a read view of the working copy, and the four edits as calls."""

    def __init__(self, kind, work: dict, where: str, idx: dict | None = None):
        self.kind, self.doc, self.where, self.edits = kind, work, where, []
        self.idx = idx if idx is not None else index(work, kind.lists)    # kept up to date by every edit

    def item(self, id_) -> dict:
        idx = self.idx
        if id_ not in idx:
            raise RostrumError.not_found(self.where, "item", id_, idx)
        return idx[id_].item

    def facts(self, item: dict) -> dict:
        """The item's facts as the document stands now (the app's kind.facts with the document): what a field's
        `valid_when` reads besides the item's own values, the same as the operation checks (_check_targets)."""
        return self.kind.facts(item, View(self.doc, self.kind.lists, self.idx))

    def _do(self, edit):
        self.edits.append(E.apply(self.doc, self.kind.lists, edit, self.where, self.idx))

    def set(self, id_, path, value):
        path = [path] if isinstance(path, str) else list(path)
        if self._already(id_, path, value):
            return                                   # setting a value to what it is changes nothing: no edit, no step
        self._do(E.Set(id_, path, value))

    def _already(self, id_, path, value) -> bool:
        node = self.idx[id_].item if id_ in self.idx else None
        for k in path:
            if not isinstance(node, dict) or k not in node:
                return False
            node = node[k]
        return type(node) is type(value) and node == value

    def insert(self, parent, key, item, index=None):
        self._do(E.Insert(item["id"], parent, key, 10**9 if index is None else index, item))

    def remove(self, id_):
        self._do(E.Remove(id_))

    def move(self, id_, parent, key, index=None):
        self._do(E.Move(id_, (), (parent, key, 10**9 if index is None else index)))

    def new_id(self, type_) -> str:
        return ids.counted(self.idx, type_)

    def fail(self, code, subject, problem, accepted=(), hint=None, plain=None):
        raise RostrumError(code, self.where, subject, problem, accepted, hint, plain)


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


def refusal(op) -> str:
    """Why an item can't take `op` now, in words (the operation's label, the fact's plain phrasing): `can't take Pin to
    frame now: it only works when it sits directly in a scene and Locked is off`."""
    return f"can't take {op.label or op.name} now: it only works when {describe(op.valid_when, {p.name: p.label for p in op.params})}"


def _check_targets(kind, op, targets, view, where):
    idx, items = view.locs(), []
    if op.targets is None:
        if targets:
            raise RostrumError(codes.BAD_ARGUMENT, where, f"target {targets}", f"{op.name} takes no target")
        return items
    if not targets:
        raise RostrumError(codes.BAD_ARGUMENT, where, "target []", f"{op.name} needs a {'/'.join(op.targets)}")
    if len(targets) < op.min_targets:
        raise RostrumError(codes.BAD_ARGUMENT, where, f"target {targets}", f"{op.name} needs {op.min_targets} or more")
    for t in targets:
        if t not in idx:
            err = RostrumError.not_found(where, '/'.join(op.targets), t,
                                         [i for i, l in idx.items() if l.item.get("type") in op.targets])
            err.hint = (kind.elsewhere(t) if kind.elsewhere else None) or err.hint
            raise RostrumError(err.code, err.where, err.subject, err.problem, err.accepted, err.hint) from None
        it = idx[t].item
        if it.get("type") not in op.targets:
            raise RostrumError(codes.BAD_ARGUMENT, where, f'target "{t}"', f"is a {it.get('type')}, not a "
                               f"{' or '.join(op.targets)}")
        if not holds(op.valid_when, fields(it, kind.lists), kind.facts(it, view)):
            raise RostrumError(codes.BAD_ARGUMENT, where, f'target "{t}"',
                               refusal(op))
        items.append(it)
    return items


def _check_valid_when(kind, op, items, args, view, where):
    """An argument that only applies sometimes must apply after this call (a value plus its switch is fine)."""
    for it in items or [{}]:
        values = {**fields(it, kind.lists), **args}
        facts = kind.facts(it, view) if it else {}
        for name in args:
            p = op.param(name)
            if not holds(p.valid_when, values, facts):
                raise RostrumError(codes.BAD_ARGUMENT, where, f'"{name}"',
                                   f"only applies when {describe(p.valid_when, {q.name: q.label for q in op.params})}",
                                   hint=f"Set that in the same call to use {name}.")


def changed_items(edits, idx, lists) -> list[dict]:
    """The items whose own values these edits set or brought in (still in the document)."""
    ids = dict.fromkeys(i for e in edits if isinstance(e, (E.Set, E.Insert))
                        for i in ([e.id] if isinstance(e, E.Set) else subtree_ids(e.item, lists)))
    return [idx[i].item for i in ids if i in idx]


def set_fields(edits) -> dict:
    """item id -> the top-level fields these edits set, for items only Set (an inserted item, or one whose kind
    changed, is checked whole). A field nobody set holds what passed the check before."""
    out, whole = {}, set()
    for e in edits:
        if isinstance(e, E.Set) and e.path[0] != "type":
            out.setdefault(e.id, set()).add(e.path[0])
        elif isinstance(e, (E.Insert, E.Set)):
            whole.add(e.id)
    for i in whole:
        out.pop(i, None)
    return out


def plan(kind, data: dict, calls, locked_by=None, who=None) -> tuple[dict, list, list[dict]]:
    """(the new document, the applied edits, the normalized calls). Pure: `data` is not touched. `locked_by(id)`: the
    Who that locked an item (Document.locked_by); `who`: who asks, so an agent can't unlock a person's lock."""
    return plan_indexed(kind, data, calls, locked_by, who)[:3]


def plan_indexed(kind, data: dict, calls, locked_by=None, who=None, idx=None, check=True):
    """plan, plus the new document's index (its positions may be stale). `idx`: data's index, when known. `check=False`:
    the whole-document check is left out (a "would this change anything?" question; applying always checks)."""
    calls = kind.registry.resolve(normalize(calls))
    work, idx = E.fork(data, kind.lists, idx)          # one index for the whole call, kept up to date by its edits
    applied, late = [], []
    for n, call in enumerate(calls, 1):
        said = call.pop("said", None)                  # an alias: errors name what the caller wrote
        where = f"op {n} of {len(calls)} ({said or call['op']})"
        op = kind.registry.get(call["op"], f"op {n} of {len(calls)}")
        view = View(work, kind.lists, idx)
        items = _check_targets(kind, op, call["target"], view, where)
        args = _check_args(op, call["args"], where)
        try:
            _check_valid_when(kind, op, items, args, view, where)
        except RostrumError as err:        # a later op of the same call may switch it on: judged on the whole result
            late.append((err, op, call["target"], args, where))
        ctx = Context(kind, work, where, idx)
        try:
            op.fn(ctx, call["target"], args)
        except RostrumError:
            raise
        except Exception as e:  # a bug in an operation is loud, never half-applied
            raise bug.internal(where, op.name, e) from e
        locks.check(ctx.edits, idx, kind.lists, where, locked_by, who)
        call["args"] = args
        applied += ctx.edits
    for err, op, target, args, where in late:
        view = View(work, kind.lists, idx)
        _check_valid_when(kind, op, [view.locs()[t].item for t in target if t in view.locs()], args, view, where)
    problems = kind.problems(work, changed_items(applied, idx, kind.lists), set_fields(applied)) if check else []
    if problems:
        raise RostrumError(codes.CHECK_FAILED, f"{len(calls)} op(s)", "the document", "would break its check: "
                           + "; ".join(problems))
    return work, applied, calls, idx
