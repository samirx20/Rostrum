"""The pieces a script merge is made of: the current value of a key, who counts as another author, the checks on a
script's output (see merge.py)."""
from __future__ import annotations

from . import edits as E
from .errors import RostrumError, codes
from .tree import index, walk
from .who import UPGRADE


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
    return (f". If that is the cause: script {names} already made some of these items. A script run again under the same name replaces what it "
            f'made, a new name ("{name}") adds a second copy. Run it under {names if len(twins) == 1 else "that script\'s"} '
            f"name to replace them, or give these items other ids.")


def _up_to_date(doc, output: dict) -> dict:
    """The script's output as an opened file would hold it (the app's upgrade: 2D moves a gradient effect into the fill)."""
    up = doc.kind.upgrade(output, doc.kind.lists, doc.folder) if doc.kind.upgrade else None
    return up[0] if up else output


def _own(doc, c, who, name: str, id_: str) -> bool:
    """Change `c` is not another author's work: this script's own run, the same agent or script (never a person: their
    own hand edits stay theirs), an older file's upgrade, or the run of a script that has handed `id_` over (the new
    scene's ground and sky, taken over by an agent's script: the starter's values are no one's edit to keep)."""
    if (c.who == who and who.kind != "person") or c.who == UPGRADE:
        return True
    return any(k.get("op") == "run_script" and ((s := (k.get("args") or {}).get("script")) == name or _handed_over(doc, s, id_))
               for k in c.calls)


def _handed_over(doc, script, id_: str) -> bool:
    """Script `script` ran before but no longer holds `id_` in its last output: another script took it over."""
    base = doc.script_bases.get(script)
    return base is not None and id_ not in index(base, doc.kind.lists)


def _other_author(doc, hit: set, who, name: str):
    """(key, change) for the first collided key whose last change is another author's, else None. Unknown counts as
    another's: a value held back wrongly is reported and can be forced; a person's work wiped is lost."""
    for key in sorted(hit):
        c = doc.who_changed(*key[:2]) if len(key) > 1 else doc.who_changed(key[0])
        if c is None or not _own(doc, c, who, name, key[0]):
            return key, c
    return None
