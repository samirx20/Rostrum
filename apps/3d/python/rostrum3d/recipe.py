"""Recipes (PR8): a script with named settings (recipe_settings.py) becomes a recipe in the scene, so a person can steer
an agent's procedural work: change "Copies" from 12 to 30 and the script runs again with it.

    doc ─ recipes ─ recipe {id, type, name, script, source, settings: [declarations], values: {name: value}}

run_script makes the recipe with the rest of what the script makes (`recipe_<script name>`), so the recipe and its
things are one merge. `set_values` / `rerun` (agents: edit_recipe; the window: the recipe's rows) run its stored script
again under its own name through the same merge as run_script: one history step (one undo), what it made replaced field
by field, never doubled, and a person's own edits to those things kept. A script with no settings makes no recipe.
"""
from __future__ import annotations

import re

from rostrum_core.errors import RostrumError, codes

from . import recipe_settings as S

LIST = "recipes"
TYPE = "recipe"


def id_for(script: str) -> str:
    stem = re.sub(r"\.py$", "", script)
    return "recipe_" + (re.sub(r"[^A-Za-z0-9_]", "_", stem) or "script")


def all_of(data: dict) -> list[dict]:
    return data.get(LIST) or []


def find(doc, recipe_id: str, where: str = "edit_recipe") -> dict:
    by_id = {r["id"]: r for r in all_of(doc.data)}
    if recipe_id not in by_id:
        raise RostrumError.not_found(where, "recipe", recipe_id, by_id, "this scene (a recipe is a script run with setting(...))")
    return by_id[recipe_id]


class Settings:
    """A run's settings (script.py's Build holds one): `setting(...)` in the script calls `take`."""

    def __init__(self, doc, script: str, asked: dict | None):
        self.asked, self.decls, self.values = dict(asked or {}), [], {}
        rec = next((r for r in all_of(doc.data) if r.get("script") == script), None) if doc is not None else None
        self.stored = {d["name"]: {"decl": d, "value": (rec.get("values") or {}).get(d["name"], d.get("default"))}
                       for d in (rec or {}).get("settings", [])}

    def take(self, name, default, min=None, max=None, label=None, choices=None):
        d = S.declare(name, default, min, max, label, choices)
        if any(x["name"] == name for x in self.decls):
            raise ValueError(f'setting "{name}" is declared twice')
        self.decls.append(d)
        self.values[name] = S.value(d, self.asked, self.stored.get(name))
        return self.values[name]

    def node(self, script: str, source: str) -> dict | None:
        """The recipe this run makes (None: the script declared no settings). A setting asked for that the script
        doesn't declare is refused (a typo would otherwise do nothing)."""
        unknown = sorted(set(self.asked) - set(self.values))
        if unknown:
            raise ValueError(f'no setting {", ".join(map(repr, unknown))} in script "{script}"; its settings: '
                             f'{", ".join(self.values) or "none"}')
        if not self.decls:
            return None
        return {"id": id_for(script), "type": TYPE, "name": script, "script": script, "source": source,
                "settings": self.decls, "values": dict(self.values)}


def check(rec: dict, values: dict, where: str = "edit_recipe") -> None:
    """Every asked value is a setting of the recipe and one it takes; else loud, naming it and what is accepted."""
    decls = {d["name"]: d for d in rec.get("settings", [])}
    for name, v in values.items():
        if name not in decls:
            raise RostrumError.not_found(where, "setting", name, decls, f'recipe "{rec["id"]}"')
        why = S.problem(decls[name], v)
        if why:
            raise RostrumError(codes.BAD_ARGUMENT, where, f'setting "{name}"', why, [S.accepted(decls[name])])


def rerun(doc, recipe_id: str, values: dict | None = None, who=None, session=None, where: str = "edit_recipe"):
    """Run the recipe's script again, with `values` changed (none: as it is). One history step. Returns
    (the merge's report, the run's notes)."""
    from .script import run_source                         # script.py imports this module
    rec = find(doc, recipe_id, where)
    check(rec, values or {}, where)
    tree = run_source(rec["source"], rec["script"], doc, values=values or {})
    return doc.run_script(rec["script"], tree, who, session=session), getattr(tree, "notes", [])


def made(doc, rec: dict) -> list[str]:
    """The ids of what the recipe's script made last, still in the scene (its own recipe aside)."""
    from rostrum_core.tree import walk
    base = doc.script_bases.get(rec["script"]) or {}
    now = {n["id"] for n in walk(doc.data, doc.kind.lists)}
    return [n["id"] for lst in ("items", "materials", "shots") for n in base.get(lst, []) if n["id"] in now]


def problems(data: dict) -> list[str]:
    """The document check's part: each recipe's values are ones its settings take."""
    out = []
    for r in all_of(data):
        decls = {d.get("name"): d for d in r.get("settings", []) if isinstance(d, dict)}
        for name, v in (r.get("values") or {}).items():
            if name not in decls:
                out.append(f'recipe {r["id"]}.values: "{name}" is not one of its settings')
            elif (why := S.problem(decls[name], v)) is not None:
                out.append(f'recipe {r["id"]}.values: setting "{name}" {why}; it takes {S.accepted(decls[name])}')
    return out
