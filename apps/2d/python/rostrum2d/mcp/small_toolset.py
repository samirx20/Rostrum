"""The four-tool server (ROSTRUM2D_TOOLSET=small): run_script, look, export, read_guide. Same engine, same script layer,
same replies; the other tools are hidden, never forked. The read-only checks stay reachable through `look`'s `check`
(their own arguments, checked by their own schema), the project through run_script's `project`, the rest from the script.

    ROSTRUM2D_TOOLSET=small python -m rostrum2d.mcp

Built to test whether a small toolset beats the full one; `full` (the default) is today's server."""
from __future__ import annotations

import dataclasses
import os
import re

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply
from rostrum_core.mcp.tools import Tools, _schema_of

from . import script_look, session_clock
from rostrum_core.mcp.tools import Tool

CHECKS = ["look_frame", "look_motion", "look_at", "look_drawing", "look_painting", "inspect_item",
          "inspect_project", "inspect_sounds", "inspect_fonts", "inspect_markers",
          "inspect_table", "inspect_job", "inspect_operations", "inspect_history"]

DOES = ["edit_document", "run_brush", "run_import", "edit_markers", "edit_sound_cue", "run_brand_kit", "run_open_project",
        "edit_undo", "run_stop"]

INSTRUCTIONS = ("rostrum-2d makes motion graphics, from one Python script. Four tools: run_script (build or rebuild the whole "
                "film from one script; `project` opens or makes the project folder; `look` sends back stills in the same reply), "
                "look (stills; `check` runs one detailed check), export (the MP4) "
                "and read_guide (the how-to guides: read 'start-here' first; `search` finds the sections about some words). "
                "Everything else (brushes, painting, bones, lip sync, markers, cameras, text, effects, imports) is a function "
                "inside the script. Write the film as one script, look, edit, re-run under the same name. Every reply ends "
                "with a clock line (time since your first call, minutes left with a budget). A reply or guide line that names "
                "a check tool (look_frame, look_motion, inspect_item, ...) means look with that `check`; a change tool (edit_document, "
                "run_brush, edit_markers, ...) means run_script with that `do`.")

NO_PROJECT = "No project is open: give run_script a `project` folder."


def wanted() -> bool:
    return os.environ.get("ROSTRUM2D_TOOLSET", "full").strip().lower() == "small"


@dataclasses.dataclass(frozen=True)
class _Open(Tool):
    """look / run_script: with `check` / `do` the other arguments belong to that part, whose own schema checks them."""
    def check(self, args, notes=None):
        args = args or {}
        part = "check" in args or "do" in args
        own = {k: v for k, v in args.items() if k in self.schema["properties"] and not (part and k not in ("check", "do", "times", "project"))}
        return {**args, **Tool.check(self, own, notes)}      # own arguments as read ("24" for a number: 24, said)


def as_tool(ctx, name: str):
    """The context as the hidden tool `name` sees it: its errors, the clock and the review read the tool's own name."""
    return dataclasses.replace(ctx, tool=name)


def _typed(args: dict, schema: dict) -> dict:
    """A check's arguments are not in look's / run_script's own schema, so agents send numbers as text ("12"); read text
    as the number or true/false the part's schema asks for (the bench's B films lost 8 calls to this). Anything else is
    left for the part's own check to refuse loudly."""
    props, out = schema.get("properties", {}), dict(args)
    for k, v in args.items():
        kinds = {props.get(k, {}).get("type")} | {s.get("type") for s in props.get(k, {}).get("anyOf", [])}
        if not isinstance(v, str):
            continue
        try:
            if "integer" in kinds and re.fullmatch(r"-?\d+", v.strip()):
                out[k] = int(v)
            elif "number" in kinds:
                out[k] = float(v)
            elif "boolean" in kinds and v.strip().lower() in ("true", "false"):
                out[k] = v.strip().lower() == "true"
        except ValueError:
            pass
    return out


def _part(ctx, tools: dict, name: str, args: dict, outer: str, key: str):
    """Run the hidden tool `name` with its own arguments, checked by its own schema; an error names outer + key."""
    part = dataclasses.replace(tools[name], name=outer)
    try:
        return tools[name].fn(as_tool(ctx, name), part.check(_typed(args, part.schema)))
    except RostrumError as e:
        if e.where.startswith(name) or e.where == outer:
            e.where = f'{outer} ({key} "{name}")'
        raise


def _look(full: Tools, clock):
    tools = {n: full.get(n) for n in CHECKS}
    plain = session_clock._wrapped(Tool("run_script", "", {}, None, lambda ctx, args: script_look.after_run(
        ctx, ctx.document(None), args["look"], Reply("Looked.", {}))), clock)

    def look(ctx, args):
        args = dict(args)
        name = args.pop("check", None)
        if name is None:
            times = args.pop("times", True)
            if args:
                raise RostrumError(codes.BAD_ARGUMENT, "look", f'"{next(iter(args))}"', "is an argument of a check, not of the plain look",
                                   ["times", "check"], 'Pass check too, e.g. {"check": "look_frame", "what": "sheet", ...}.')
            doc = ctx.document(None)
            return plain(as_tool(ctx, "run_script"), {"look": times})
        return _part(ctx, tools, name, args, "look", "check")

    schema = {"properties": {
        "check": {"type": "string", "enum": CHECKS, "description": "A detailed check, with its own arguments beside it "
                  "(read_guide 'tool-reference' lists each one's arguments). Without it: a contact sheet."},
        "times": {"anyOf": [{"type": "boolean"}, {"type": "array", "items": {"type": "number", "minimum": 0}, "minItems": 1, "maxItems": 12}],
                  "description": "Plain look: the seconds to show (or true: 6 moments spread over the film)."}},
        "additionalProperties": True}
    text = ("See the film: with no `check`, one contact sheet (`times`, default 6 moments spread over it) . With `check` one detailed check and its own arguments: "
            "look_frame (a frame, sheet, the world, what is in frame, rig, empty spans, review: what the checks measure, diagnose, "
            "layout, swaps), look_motion (moves, paths, curves, keys), look_at (what is at a point), look_drawing / "
            "look_painting (paint, coverage, strokes landed), inspect_item / inspect_project / inspect_markers / inspect_sounds / "
            "inspect_fonts / inspect_table / inspect_job / inspect_operations / inspect_history. "
            'E.g. {"check": "look_frame", "time": 2.5}. Arguments: read_guide \'tool-reference\'.')
    return look, schema, text


def _run_script(full: Tools):
    run, opener = full.get("run_script"), full.get("run_open_project")
    does = {n: full.get(n) for n in DOES}
    props = {**run.schema["properties"], "project": {"type": "string", "description":
             "Open this project folder first (absolute path; made with an empty document when it doesn't exist yet), "
             "e.g. \"C:/work/launch\"; later calls keep it open."},
             "do": {"type": "string", "enum": DOES, "description": "Instead of a script, one direct change with its own "
                    "arguments beside it (read_guide 'tool-reference'): edit_document (operations, e.g. paint.stroke on a shape), "
                    "run_brush (saved brushes), run_import (svg / pdf / psd / figma), edit_markers, edit_sound_cue, run_brand_kit, "
                    "run_open_project (recent projects), edit_undo, run_stop."}}

    def run_script(ctx, args):
        args = dict(args)
        if "project" in args:
            opened = opener.fn(as_tool(ctx, "run_open_project"), opener.check({"folder": args.pop("project")}))
            if not any(k in args for k in ("source", "path", "name", "do")):
                return opened
        if "do" in args:
            return _part(ctx, does, args.pop("do"), args, "run_script", "do")
        return run.fn(as_tool(ctx, "run_script"), run.check(args))
    return run_script, {**run.schema, "properties": props}, (run.description + " `project` opens or makes the project "
                                                             "folder first; `do` makes one direct change instead of a script.")


def _read_guide(full: Tools):
    guide = full.get("inspect_guide")

    def read_guide(ctx, args):
        if "search" not in args:
            return guide.fn(as_tool(ctx, "inspect_guide"), args)
        words = [w for w in re.findall(r"\w+", args["search"].lower()) if len(w) > 2]
        g, hits = ctx.app.guides, []
        for topic in g.topics():
            for part in re.split(r"(?m)^(?=## )", g.get(topic))[1:]:
                low = part.lower()
                score = sum(low.count(w) for w in words) + 5 * sum(w in part.splitlines()[0].lower() for w in words)
                if score and sum(w in low for w in words) * 2 >= len(words):
                    hits.append((score, topic, part.splitlines()[0].lstrip("# ").strip()))
        hits.sort(reverse=True)
        rows = [{"topic": t, "section": s} for _, t, s in hits[:12]]
        return Reply(f"{len(hits)} sections match; best first:\n" + "\n".join(f"- read_guide topic \"{r['topic']}\" section \"{r['section']}\"" for r in rows)
                     if rows else "No section matches; read_guide with no topic lists the guides.", {"hits": rows})
    schema = {**guide.schema, "properties": {**guide.schema["properties"], "search": {"type": "string", "description":
              "Words to find, e.g. \"brush lettering\": the guide sections that talk about them, best first."}}}
    return read_guide, schema, ("The how-to guides: {\"topic\": \"start-here\"} first; with no topic, the list; `section` "
                                "gives one section; `search` finds the sections about some words across every guide.")


def _export(full: Tools):
    export = full.get("render_export")
    return (lambda ctx, args: export.fn(as_tool(ctx, "render_export"), args)), export.schema, export.description


def apply(runtime, clock) -> None:
    """Swap the runtime's tools for the four. Call after every wrapper is on (export's wait and beats, the clock): the
    four call the wrapped tools under their own names, so replies, errors and the clock read exactly as in the full set."""
    full = runtime.tools
    small = Tools()
    made = {"run_script": _run_script(full), "look": _look(full, clock), "export": _export(full), "read_guide": _read_guide(full)}
    for name, (fn, schema, text) in made.items():
        spec, _ = _schema_of(schema)
        small._tools[name] = (_Open if name in ("look", "run_script") else Tool)(name, text, spec, None, fn)       # look / export: one-word names, outside the verb_thing rule
    small._renamed = {n: ("look", f'check: "{n}"') if n in CHECKS else ("run_script", f'do: "{n}"' if n in DOES else "a function inside the script")
                      for n in full._tools if n not in made}
    small._renamed.update(render_export=("export", None), inspect_guide=("read_guide", None),
                          run_open_project=("run_script", 'project: "<folder>"'))
    runtime.tools = small
    from . import guides_small
    from .server import GUIDES
    runtime.app.guides = guides_small.load_b_guides(GUIDES, full)     # the same guides, call lines in B's form
