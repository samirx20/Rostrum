"""Re-running a script never wipes a person's work (OPERATIONS.md § 7).

    B = what this script produced last time      N = what it produces now      C = the document now
    the script's changes = diff(B, N); everyone else's = diff(B, C)
    apply the script's changes to C, except where they collide with everyone else's.

A collision keeps the other author's value and is reported ("logo.x: script says 400, kept 620 (person:sam,
"Move logo")"). `force=True` or `force=["logo.x", "logo"]` lets the script win there. B moves forward only by
what was applied, so a held-back change is reported again next run.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field

from . import edits as E
from .diff import diff
from .errors import RostrumError, codes
from .tree import index, walk


@dataclass
class MergeReport:
    script: str
    change: object = None                       # the Change, or None when nothing new applied
    applied: int = 0
    held: list = field(default_factory=list)    # {"key", "script", "kept", "who", "label"}
    removed: list = field(default_factory=list) # {"id", "type"}: the items the run took out (topmost ones)

    def warnings(self) -> list:
        """One line per thing a caller must not miss: each held-back value, and what the run took out."""
        held = [f'Held back "{h["key"]}": {h["who"]} set it to {h["kept"]!r}, the script wanted {h["script"]!r}. '
                f'Pass force: ["{h["key"]}"] to overwrite.' for h in self.held]
        gone = [f'Removed "{r["id"]}" ({r["type"]}): the script no longer makes it.' for r in self.removed]
        return held + gone

    def summary(self) -> str:
        text = f"Script {self.script}: {self.applied} change(s) applied"
        if self.removed:
            text += "; removed: " + ", ".join(f"{r['id']} ({r['type']})" for r in self.removed)
        if not self.held:
            return text + "."
        lines = [f"  {h['key']}: script says {h['script']!r}, kept {h['kept']!r} ({h['who']}, \"{h['label']}\")"
                 for h in self.held]
        return text + f", {len(self.held)} held back to keep other people's work:\n" + "\n".join(lines) + \
            "\nChange them with an operation, or run again with force=[...] to let the script win."


def _forced(force, ks) -> bool:
    if force is True:
        return True
    wanted = {tuple(f.split(".")) for f in (force or [])}
    return bool(E.overlap(ks, wanted))


def _current(data, lists, key):
    loc = index(data, lists).get(key[0])
    if loc is None:
        return "(removed)"
    node = loc.item
    for k in key[1:]:
        if k == "@place":
            return f"in {loc.parent}.{loc.key}"
        if not isinstance(node, dict) or k not in node:
            return E.MISSING
        node = node[k]
    return "(kept, edited)" if len(key) == 1 else node


def _script_value(e):
    if isinstance(e, E.Set):
        return e.value
    return {E.Remove: "(remove)", E.Insert: "(add)", E.Move: "(move)"}[type(e)]


def _record(base, lists, e, name, idx):
    """Move B forward by one edit. An edit inside an item B doesn't hold (its insert was held back) can't be
    recorded and isn't: it is simply compared again on the next run."""
    try:
        E.apply(base, lists, e, f"run_script {name} (record)", idx)
    except RostrumError as err:
        if err.code != codes.NOT_FOUND:
            raise


def check_output(kind, output: dict, where: str):
    """A script's values obey the same parameter rules as operation arguments (no side door)."""
    index(output, kind.lists)                             # duplicate ids: loud
    for bad in kind.bad_values(walk(output, kind.lists)):
        raise bad.within(where)


def check_kinds(base: dict, output: dict, lists, where: str):
    """An id keeps its kind across runs. Rewriting a light as a mesh in place would carry its history, links and
    a person's held edits over to a different thing, so it is refused before anything applies."""
    before = index(base, lists)
    for id_, loc in index(output, lists).items():
        was = before.get(id_)
        if was is not None and was.item.get("type") != loc.item.get("type"):
            raise RostrumError(codes.BAD_ARGUMENT, where, f'id "{id_}"',
                               f'was a {was.item.get("type")} last run and is a {loc.item.get("type")} now',
                               hint="Use a new id for the new kind (or remove the old one first).")


def merge_script(doc, name, output: dict, who, force=False, session=None) -> MergeReport:
    lists = doc.kind.lists
    base = doc.script_bases.get(name) or doc.kind.blank()
    check_output(doc.kind, output, f"run_script {name}")
    check_kinds(base, output, lists, f"run_script {name}")
    others = diff(base, doc.data, lists)
    other_keys = set().union(*(E.keys(e, lists) for e in others)) if others else set()
    work, new_base = copy.deepcopy(doc.data), copy.deepcopy(base)
    idx, base_idx = index(work, lists), index(new_base, lists)     # each kept up to date by its edits
    report, applied = MergeReport(name), []
    for e in diff(base, output, lists):
        ks = E.keys(e, lists)
        if isinstance(e, E.Set) and _current(work, lists, (e.id, *e.path)) == e.value:
            _record(new_base, lists, e, name, base_idx)                              # everyone already agrees
            continue
        hit = E.overlap(ks, other_keys)
        if hit and not _forced(force, ks):
            key = sorted(hit)[0]
            c = doc.who_changed(*key[:2]) if len(key) > 1 else doc.who_changed(key[0])
            report.held.append({"key": E.key_text(key), "script": _script_value(e),
                                "kept": _current(work, lists, key), "who": str(c.who) if c else "?",
                                "label": c.label if c else "?"})
            continue
        try:
            applied.append(E.apply(work, lists, e, f"run_script {name}", idx))
        except RostrumError as err:
            if err.code not in (codes.NOT_FOUND, codes.CONFLICT):
                raise
            report.held.append({"key": E.key_text(sorted(ks)[0]), "script": _script_value(e),
                                "kept": "(its place is gone)", "who": "?", "label": err.problem})
            continue
        _record(new_base, lists, e, name, base_idx)
    problems = doc.kind.check(work)
    if problems:
        raise RostrumError(codes.CHECK_FAILED, f"run_script {name}", "the merged document",
                           "would break its check: " + "; ".join(problems))
    doc.script_bases[name] = new_base
    report.applied = len(applied)
    report.removed = [{"id": a.id, "type": a.item.get("type", "item")} for a in applied if isinstance(a, E.Remove)]
    if applied:
        call = {"op": "run_script", "target": [], "args": {"script": name, "force": force}}
        report.change = doc.commit(work, applied, who, f"Run {name}", [call], session)
    return report
