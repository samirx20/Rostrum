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
so a run never writes what the next open would rewrite.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import edits as E
from .diff import diff
from .errors import RostrumError, codes
from .tree import bare, index, walk
from .who import UPGRADE


SHOWN = 5   # names a reply lists before saying "and N more"
GONE = "(its place is gone)"   # a held edit that could not land at all (its parent is gone, its id is taken)


def _owner(r: dict) -> str:
    """Who an item belongs to: a key's id is `owner.field.k1500`, so its owner is the first part; any other item is its own."""
    return r["id"].split(".")[0] if r.get("type") == "key" else r["id"]


def _span(names: list) -> str:
    return names[0] if len(names) == 1 else f"{names[0]}–{names[-1]}" if len(names) > 2 else " and ".join(names)


def removed_text(removed: list) -> str:
    """What a run took out, in a line: counts per kind with the layers they were on ("98 keys on pollen0–pollen55"), then
    the first few ids. The full list is `data.removed` when asked for (`detail`)."""
    kinds: dict[str, list] = {}
    for r in removed:
        kinds.setdefault(r["type"], []).append(r)
    parts = []
    for kind, items in kinds.items():
        owners = list(dict.fromkeys(_owner(r) for r in items))
        on = "" if kind != "key" else f" on {_span(owners)}"
        parts.append(f"{len(items)} {kind}{'s' * (len(items) != 1)}{on}")
    first = ", ".join(r["id"] for r in removed[:SHOWN])
    more = f" and {len(removed) - SHOWN} more" if len(removed) > SHOWN else ""
    return f"{', '.join(parts)} (first: {first}{more})"


_WANTS = {"(add)": "add it", "(remove)": "remove it", "(move)": "move it"}


def held_words(h: dict) -> str:
    """One held-back thing in words: placeholders like "(add)" / "(kept, edited)" say who got there first instead."""
    name = h["who"] if h["who"] not in ("?", None) else "someone else (a person or agent; the history doesn't say who, e.g. the change was made inside it or before the file was opened)"
    who = f'{name} ("{h["label"]}")' if h["label"] not in ("?", None) else name
    if h["kept"] == GONE:                   # not someone's work: the edit can't land (force can't help either)
        return (f'{h["key"]}: the script could not {_WANTS.get(h["script"], "set it").replace(" it", "")} it: {h["label"]} '
                "(force can't help: remove or rename what is in its way, or give the script's item another id)")
    if h["script"] in _WANTS:
        return f'{h["key"]}: the script wanted to {_WANTS[h["script"]]}, but it was already changed by {who}'
    if h["kept"] == "(kept, edited)":
        return f'{h["key"]}: script says {h["script"]!r}, but it was already added or edited by {who}'
    return f'{h["key"]}: script says {h["script"]!r}, kept {h["kept"]!r} ({who})'


@dataclass
class MergeReport:
    script: str
    change: object = None                       # the Change, or None when nothing new applied
    applied: int = 0
    held: list = field(default_factory=list)    # {"key", "script", "kept", "who", "label"}
    removed: list = field(default_factory=list) # {"id", "type"}: the items the run took out (topmost ones)
    others: list = field(default_factory=list)  # first run under this name: the names of the scripts that already made things

    def warnings(self) -> list:
        """One line per thing a caller must not miss: each held-back value, what the run took out, and that a new
        script name adds beside what earlier scripts made instead of replacing it."""
        held = [f'Held back {held_words(h)}.' + ("" if h["kept"] == GONE else f' Pass force: ["{h["key"]}"] to take over.')
                for h in self.held]
        gone = [f"Removed {removed_text(self.removed)}: the script no longer makes them."] if self.removed else []
        new = [f'"{self.script}" is a new script name, so it ADDED its items beside what {", ".join(self.others)} made. '
               f"To change those instead, run again under their name (a script re-run under the same name replaces what it made)."] if self.others else []
        return held + gone + new

    def summary(self) -> str:
        text = f"Script {self.script}: {self.applied} change(s) applied"
        if self.removed:
            text += f"; removed {removed_text(self.removed)}"
        if not self.held:
            return text + "."
        lines = [f"  {held_words(h)}" for h in self.held]
        keys = ", ".join(f'"{h["key"]}"' for h in self.held if h["kept"] != GONE)
        win = (f"\nTo let the script win, run again with force: [{keys}] (or force: true for all); or change them with an "
               "operation." if keys else "")
        return text + f", {len(self.held)} held back:\n" + "\n".join(lines) + win


def _forced(force, ks) -> bool:
    if force is True:
        return True
    wanted = {tuple(f.split(".")) for f in (force or [])}
    return bool(E.overlap(ks, wanted))


def _current(data, lists, key, idx=None):
    """`idx`: data's index when kept already (the merge's): one lookup, not an index of the whole tree per edit."""
    loc = (index(data, lists) if idx is None else idx).get(key[0])
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


def twin_hint(doc, name: str, output: dict) -> str:
    """When a merge fails: the other scripts that already made some of these ids (a script under a new name adds a second
    copy instead of replacing the first), and what to do."""
    ids = {i["id"] for i in walk(output, doc.kind.lists)}
    twins = [n for n, b in doc.script_bases.items() if n != name and ids & {i["id"] for i in walk(b, doc.kind.lists)}]
    if not twins:
        return ""
    names = ", ".join(f'"{n}"' for n in twins)
    return (f"script {names} already made some of these items. A script run again under the same name replaces what it "
            f'made, a new name ("{name}") adds a second copy. Run it under {names if len(twins) == 1 else "that script\'s"} '
            f"name to replace them, or give these items other ids. The check says: ")


def _up_to_date(doc, output: dict) -> dict:
    """The script's output as an opened file would hold it (the app's upgrade: 2D moves a gradient effect into the fill)."""
    up = doc.kind.upgrade(output, doc.kind.lists, doc.folder) if doc.kind.upgrade else None
    return up[0] if up else output


def _own(c, who, name: str) -> bool:
    """Change `c` is not another author's work: this script's own run, the same agent or script (never a person: their
    own hand edits stay theirs), or an older file's upgrade."""
    if (c.who == who and who.kind != "person") or c.who == UPGRADE:
        return True
    return any(k.get("op") == "run_script" and (k.get("args") or {}).get("script") == name for k in c.calls)


def _other_author(doc, hit: set, who, name: str):
    """(key, change) for the first collided key whose last change is another author's, else None. Unknown counts as
    another's: a value held back wrongly is reported and can be forced; a person's work wiped is lost."""
    for key in sorted(hit):
        c = doc.who_changed(*key[:2]) if len(key) > 1 else doc.who_changed(key[0])
        if c is None or not _own(c, who, name):
            return key, c
    return None


def merge_script(doc, name, output: dict, who, force=False, session=None) -> MergeReport:
    lists = doc.kind.lists
    base = doc.script_bases.get(name) or doc.kind.blank()
    output = _up_to_date(doc, output)
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
    if problems:
        raise RostrumError(codes.CHECK_FAILED, f"run_script {name}", "the merged document",
                           "would break its check: " + twin_hint(doc, name, output) + "; ".join(problems))
    first_run = name not in doc.script_bases
    doc.script_bases[name] = new_base
    report.applied = len(applied)
    if first_run and applied:
        report.others = [n for n in doc.script_bases if n != name]
    report.removed = [{"id": a.id, "type": a.item.get("type", "item")} for a in applied if isinstance(a, E.Remove)]
    if applied:
        call = {"op": "run_script", "target": [], "args": {"script": name, "force": force}}
        report.change = doc.commit(work, applied, who, f"Run {name}", [call], session)
    return report
