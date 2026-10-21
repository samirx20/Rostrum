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
from .tree import fields, index, walk


@dataclass
class MergeReport:
    script: str
    change: object = None                       # the Change, or None when nothing new applied
    applied: int = 0
    held: list = field(default_factory=list)    # {"key", "script", "kept", "who", "label"}

    def summary(self) -> str:
        text = f"Script {self.script}: {self.applied} change(s) applied"
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


def check_output(kind, output: dict, where: str):
    """A script's values obey the same parameter rules as operation arguments (no side door)."""
    index(output, kind.lists)                             # duplicate ids: loud
    for item in walk(output, kind.lists):
        op = kind.registry.field_op(item.get("type"))
        for k, v in (fields(item, kind.lists).items() if op else ()):
            if op.param(k):
                op.param(k).check(v, f"{where} › {item['id']}")


def merge_script(doc, name, output: dict, who, force=False, session=None) -> MergeReport:
    lists = doc.kind.lists
    base = doc.script_bases.get(name) or doc.kind.blank()
    check_output(doc.kind, output, f"run_script {name}")
    others = diff(base, doc.data, lists)
    other_keys = set().union(*(E.keys(e, lists) for e in others)) if others else set()
    work, new_base = copy.deepcopy(doc.data), copy.deepcopy(base)
    report, applied = MergeReport(name), []
    for e in diff(base, output, lists):
        ks = E.keys(e, lists)
        if isinstance(e, E.Set) and _current(work, lists, (e.id, *e.path)) == e.value:
            E.apply(new_base, lists, e, f"run_script {name} (record)")   # everyone already agrees
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
            applied.append(E.apply(work, lists, e, f"run_script {name}"))
        except RostrumError as err:
            if err.code not in (codes.NOT_FOUND, codes.CONFLICT):
                raise
            report.held.append({"key": E.key_text(sorted(ks)[0]), "script": _script_value(e),
                                "kept": "(its place is gone)", "who": "?", "label": err.problem})
            continue
        E.apply(new_base, lists, e, f"run_script {name} (record)")
    problems = doc.kind.check(work)
    if problems:
        raise RostrumError(codes.CHECK_FAILED, f"run_script {name}", "the merged document",
                           "would break its check: " + "; ".join(problems))
    doc.script_bases[name] = new_base
    report.applied = len(applied)
    if applied:
        call = {"op": "run_script", "target": [], "args": {"script": name, "force": force}}
        report.change = doc.commit(work, applied, who, f"Run {name}", [call], session)
    return report
