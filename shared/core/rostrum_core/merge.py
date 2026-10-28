"""Re-running a script never wipes a person's work (OPERATIONS.md § 7).

    B = what this script produced last time      N = what it produces now      C = the document now
    the script's changes = diff(B, N); everyone else's = diff(B, C)
    apply the script's changes to C, except where they collide with everyone else's.

A collision keeps the other author's value and is reported ("logo.x: script says 400, kept 620 (person:sam,
"Move logo")"). `force=True` or `force=["logo.x", "logo"]` lets the script win there. B moves forward only by
what was applied, so a held-back change is reported again next run.

Only another author's work holds a value back. A difference between B and C whose last change was this script's own
run, the same agent's or script's (re-running its script; a person's hand edits always count) or an older file brought up to date (who.UPGRADE) is nobody
else's, and the script's new value goes in. The output is brought up to date the same way first (the app's `upgrade`),
so a run never writes what the next open would rewrite. An item the script makes again under a new id only (Sound: a
note's id is its start in ms, so a new tempo renames it) keeps its old id (merge_ids.py), so edits to it carry over.
"""
from __future__ import annotations

from . import edits as E
from . import merge_ids
from .diff import diff
from .errors import RostrumError, codes
from .tree import bare
from .merge_report import GONE, SHOWN, MergeReport, held_words, removed_text  # noqa: F401  (one import for apps)
from .merge_checks import (_current, _forced, _other_author, _record, _script_value, _up_to_date, check_kinds,
                           check_output, twin_hint)


def merge_script(doc, name, output: dict, who, force=False, session=None) -> MergeReport:
    lists = doc.kind.lists
    base = doc.script_bases.get(name) or doc.kind.blank()
    output = merge_ids.carried(base, _up_to_date(doc, output), lists)     # an item only renamed is the same item
    check_output(doc.kind, output, f"run_script {name}")
    check_kinds(base, output, lists, f"run_script {name}")
    others = diff(base, doc.data, lists)
    other_keys = set().union(*(E.keys(e, lists) for e in others)) if others else set()
    work, idx = E.fork(doc.data, lists, doc.locs())        # versions sharing every item no edit touches (edits.fork),
    new_base, base_idx = E.fork(base, lists)                # each index kept up to date by its edits
    report, applied = MergeReport(name), []
    for e in diff(base, output, lists):
        ks = E.keys(e, lists)
        now = _current(work, lists, (e.id, *e.path), idx) if isinstance(e, E.Set) else None
        if isinstance(e, E.Set) and now == e.value:          # everyone already agrees: B takes the value as the
            _record(new_base, lists, E.Set(e.id, e.path, now, e.before), name, base_idx)   # document writes it (0, 0.0)
            continue
        if (isinstance(e, E.Remove) and e.id not in idx) or (  # already gone, or already there just as the script
                isinstance(e, E.Insert) and e.id in idx and idx[e.id].parent == e.parent   # makes it (an older
                and bare(idx[e.id].item, lists) == e.item):                                 # file's upgrade did it)
            _record(new_base, lists, e, name, base_idx)
            continue
        hit = E.overlap(ks, other_keys)
        held_by = _other_author(doc, hit, who, name) if hit and not _forced(force, ks) else None
        if held_by:
            key, c = held_by
            report.held.append({"key": E.key_text(key), "script": _script_value(e),
                                "kept": _current(work, lists, key, idx), "who": str(c.who) if c else "?",
                                "label": c.label if c else "?"})
            continue
        try:
            applied.append(E.apply(work, lists, e, f"run_script {name}", idx))
        except RostrumError as err:
            if err.code not in (codes.NOT_FOUND, codes.CONFLICT):
                raise
            report.held.append({"key": E.key_text(sorted(ks)[0]), "script": _script_value(e),
                                "kept": GONE, "who": "?", "label": err.problem})
            continue
        _record(new_base, lists, e, name, base_idx)
    problems = doc.kind.check(work)
    if problems:                          # all or nothing: a run that breaks the check changes nothing. A problem the
        had = set(doc.kind.check(doc.data))   # document had before (an older file) is not this run's: named, not blamed
        new = [p for p in problems if p not in had]
        if new:
            raise RostrumError(codes.CHECK_FAILED, f"run_script {name}", "the merged document",
                               "would break its check, so nothing was merged: " + "; ".join(new) + twin_hint(doc, name, output)
                               + (f" (already broken before this run, not by it: {'; '.join(sorted(had))})" if had else ""))
        report.broken = sorted(had)
    first_run = name not in doc.script_bases
    doc.script_bases[name] = new_base
    report.applied = len(applied)
    if first_run and applied:
        report.others = [n for n in doc.script_bases if n != name]
    report.removed = [{"id": a.id, "type": a.item.get("type", "item")} for a in E.flat(applied) if isinstance(a, E.Remove)]
    if applied:
        call = {"op": "run_script", "target": [], "args": {"script": name, "force": force}}
        report.change = doc.commit(work, applied, who, f"Run {name}", [call], session)
    return report
