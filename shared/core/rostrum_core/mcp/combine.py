"""One tool from several: an argument (`what`) picks the job (CONVENTIONS § 2: few tools, each clear).

    combine(tools, "look_frame", "See the composition: one frame, a contact sheet, the whole world ...",
            {"frame": "look_frame", "sheet": "look_sheet", "world": "look_world"}, default="frame")

The parts stay plain registered tools until this call takes them out: the new tool's arguments are every part's, its
description lists each choice with that part's own words (so nothing an agent read before is lost), and a call is
checked against the chosen part's own schema (its required arguments, its types) before it runs. Each old name then
answers with an error naming the new tool and the argument to pass (never silently works).
"""
from __future__ import annotations

from dataclasses import replace

from ..errors import RostrumError, codes
from .tools import Tool, Tools


def _arguments(parts: dict[str, Tool], key: str) -> dict:
    """Every part's arguments. One used by only some choices says which; one whose words differ per choice says each
    choice's words, and one whose type differs keeps only those words (the chosen part's own schema checks it)."""
    users: dict[str, list] = {}
    for w, t in parts.items():
        for k, v in t.schema.get("properties", {}).items():
            if k == key:
                raise RostrumError(codes.BAD_ARGUMENT, "tool registration", f'"{t.name}"', f'already has an argument "{key}"')
            users.setdefault(k, []).append((w, v))
    out = {}
    for k, uses in users.items():
        bare = [{x: y for x, y in v.items() if x != "description"} for _, v in uses]
        words = {v.get("description", "") for _, v in uses}
        arg = dict(bare[0]) if all(b == bare[0] for b in bare) else {}
        if len(words) == 1:
            said = words.pop()
            if len(uses) < len(parts):
                said = f'{said} (for {key} {", ".join(chr(34) + w + chr(34) for w, _ in uses)})'.strip()
        else:
            said = " ".join(f'With {key} "{w}": ' + (v.get("description") or v.get("type", "")).rstrip(".") + "." for w, v in uses)
        out[k] = {**arg, **({"description": said} if said else {})}
    return out


def combine(tools: Tools, name: str, lead: str, parts: dict[str, str], key: str = "what", default: str | None = None) -> Tool:
    """Replace the registered tools `parts` ({choice: tool name}) by one tool `name`; `lead` is its first sentence."""
    taken = {w: tools.take(n) for w, n in parts.items()}
    pick = {"type": "string", "enum": list(parts), "description": "Which one: "
            + ", ".join(f'"{w}"' for w in parts) + (f' (default "{default}")' if default else "") + "; each is described in the tool's description."}
    if default:
        pick["default"] = default
    schema = {"properties": {key: pick, **_arguments(taken, key)}, **({} if default else {"required": [key]})}
    text = lead.strip() + "\n\n" + "\n".join(f'- {key} "{w}": {" ".join(t.description.split())}' for w, t in taken.items())

    def run(ctx, args):
        w = args.get(key, default)
        part = replace(taken[w], name=name)
        rest = {k: v for k, v in args.items() if k != key}
        try:
            checked = part.check(rest)
        except RostrumError as e:
            e.where = f'{name} ({key} "{w}")'
            if e.problem == "is not an argument of this tool":
                e.problem = f'is not an argument of {name} with {key} "{w}"'
            raise
        try:
            return taken[w].fn(ctx, checked)
        except RostrumError as e:                  # a part that names itself by its old name: say the tool to call
            old = parts[w]
            if old != name and e.where.startswith(old):
                e.where = f'{name} ({key} "{w}")' + e.where[len(old):]
            raise

    tool = tools.add(name, run, schema, text)
    for w, n in parts.items():
        if n != name:
            tools.renamed(n, name, f'{key}: "{w}"')
    return tool
