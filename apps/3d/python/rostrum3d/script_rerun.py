"""Edit-and-re-run, made safe (script.py's Build calls these): a script's re-run under its name replaces what it made,
so the usual way to work is "write the whole scene as one script, look, edit, re-run".

- Made again under an id already in the scene (another script's, the new scene's, or one left over from an undo or a
  failed run): this run takes it over and replaces it, field by field; never a second copy, never "already in this
  document". A field a person changed since is kept (held back by the merge, or here when no script holds it).
- Ids counted for things the script leaves unnamed (mesh_1 …) skip ids other things in the scene already use.
- A re-run that leaves out most of what its last run made (2 or more things, more than half) is refused, naming them:
  a one-line tweak sent under the script's name would otherwise remove the rest. `remove("a", "b")` says it is meant.
"""
from __future__ import annotations

import copy

from rostrum_core.errors import RostrumError, codes
from rostrum_core.tree import walk

from .kind import KIND

ROOT_LISTS = ("items", "materials", "shots")


def in_scene(doc, lst: str, id_: str) -> dict | None:
    return next((n for n in doc.data.get(lst, []) if n.get("id") == id_), None)


def reserved(doc, name: str) -> set[str]:
    """Ids a counted id must skip: everything in the scene this script didn't make (its own keep their names)."""
    if doc is None:
        return set()
    mine = {n["id"] for n in walk(doc.script_bases.get(name) or KIND.blank(), KIND.lists)}
    return {n["id"] for n in walk(doc.data, KIND.lists)} - mine


def remade(b) -> None:
    """Things this run makes under an id already directly in the scene, not yet this script's: taken over (b.owned)."""
    base = b.doc.script_bases.get(b.name) or {}
    for lst in ROOT_LISTS:
        for n in b.root[lst]:
            if n["id"] in b.owned or in_scene(b.doc, lst, n["id"]) is None:
                continue
            if not any(m.get("id") == n["id"] for m in base.get(lst, [])):
                b.owned[n["id"]] = lst


def unheld_copy(doc, lst: str, id_: str, made: dict | None) -> dict:
    """The base copy of a thing no script holds (left by an undo or a failed run): the scene's own, except that a field a
    person changed last takes the script's value, so the merge leaves the person's value where it is."""
    now = copy.deepcopy(in_scene(doc, lst, id_))
    for k, v in list(now.items()):
        c = doc.who_changed(id_, k)
        if c is not None and c.who.kind == "person" and made is not None and k in made and not isinstance(v, list):
            now[k] = copy.deepcopy(made[k])
    return now


def dropped(b) -> list[tuple[str, str]]:
    """(id, kind) of what this script's last run made, still in the scene, that this run neither makes nor removes."""
    base = b.doc.script_bases.get(b.name) if b.doc is not None else None
    if not base:
        return []
    out = []
    for lst in ROOT_LISTS:
        now = {n["id"] for n in b.root[lst]}
        out += [(n["id"], n.get("type", "item")) for n in base.get(lst, [])
                if n["id"] not in now and n["id"] not in b.removing and in_scene(b.doc, lst, n["id"]) is not None]
    return out


def guard(b) -> None:
    """Refuse a re-run that would take out most of what the script made (see the module's note)."""
    gone = dropped(b)
    base = b.doc.script_bases.get(b.name) if b.doc is not None else None
    last = sum(1 for lst in ROOT_LISTS for n in (base or {}).get(lst, []) if in_scene(b.doc, lst, n["id"]) is not None)
    if len(gone) < 2 or len(gone) * 2 <= last:
        return
    names = ", ".join(f'"{i}"' for i, _ in gone)
    raise RostrumError(
        codes.BAD_ARGUMENT, "", f'script "{b.name}"',
        f"would remove {len(gone)} of the {last} things its last run made ({names}), so nothing was changed. A re-run "
        "under the same name replaces everything the script made: send the whole script with your edit",
        hint=f'To change a few things only, run a short script under a NEW name with edit("id", …). If removing them is '
             f'meant, add remove({names}) to the script.')
