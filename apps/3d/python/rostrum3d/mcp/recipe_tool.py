"""edit_recipe: an agent changes a recipe's settings, as a person does in its rows (recipe.py). One undo step; the
recipe's script runs again under its own name, so what it made is replaced field by field and a person's edits stay.

    edit_recipe {}                                       the scene's recipes, their settings and values
    edit_recipe {recipe: "recipe_fence", set: {count: 30}}   change settings and re-run
    edit_recipe {recipe: "recipe_fence"}                 re-run as it is
"""
from __future__ import annotations

from rostrum_core.mcp import Reply, Tools

from rostrum3d import recipe, recipe_settings as S

tools = Tools()


def row(doc, r: dict) -> dict:
    return {"recipe": r["id"], "script": r["script"], "values": r.get("values", {}),
            "settings": [{"name": d["name"], "label": d["label"], "takes": S.accepted(d)} for d in r.get("settings", [])],
            "made": recipe.made(doc, r)}


@tools.tool("edit_recipe", {"properties": {
    "item": {"type": "string", "description": "Project item id; default the open document."},
    "recipe": {"type": "string", "description": "The recipe's id (recipe_<script name>). Left out: the scene's recipes are listed."},
    "set": {"type": "object", "description": "{setting name: new value}. Left out: the recipe runs again as it is."}}})
def edit_recipe(ctx, args):
    """A recipe is a script run with setting(...) calls (guide 'script', Recipes). Change its settings and it runs again: one undo
    step, what it made replaced (never doubled), a person's own edits kept. No recipe: lists them."""
    doc = ctx.document(args.get("item"))
    if "recipe" not in args:
        rows = [row(doc, r) for r in recipe.all_of(doc.data)]
        return Reply(f"{len(rows)} recipe{'s' * (len(rows) != 1)}: " + (", ".join(r["recipe"] for r in rows) or
                     "none (a script with setting(...) calls makes one)"), {"recipes": rows})
    report, notes = recipe.rerun(doc, args["recipe"], args.get("set") or {}, ctx.who, ctx.group, ctx.tool)
    changed = {"seq": report.change.seq, "ops": ["run_script"], "group": report.change.session} if report.change else None
    said = ", ".join(f"{k} = {v}" for k, v in (args.get("set") or {}).items()) or "run again as it is"
    return Reply(f'Recipe {args["recipe"]}: {said}. {report.summary()}', {"recipe": row(doc, recipe.find(doc, args["recipe"])), "held": [dict(h) for h in report.held],
                                    "seq": doc.seq}, warnings=[*notes, *report.warnings()], changed=changed)
