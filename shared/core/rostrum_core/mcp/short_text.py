"""Short tool text (CONVENTIONS § 10: a description at most 150 words). An app keeps the full account in each tool's own
docstring and argument texts, and gives a table of short words; these helpers put the short words in the tool list and
make the full account a guide page (`tools-in-detail`), so the long words have one home and nothing is lost.

    tools = tidy(group(shorten(parts, say, arg, arg_of)), joined_names, plain)
    guides.add("tools-in-detail", detail_page(parts, groups, intro))

`say` {tool: sentence}; `arg` {argument: words} for every tool that has it; `arg_of` {(tool, argument): words}. Words ""
mean none (the name and type say it). An argument in neither table keeps its own first sentence, cut to `most` words.
"""
from __future__ import annotations

import dataclasses
import re

from .tools import Tools, _schema_of

_FOR = re.compile(r'\(for what ((?:"\w+"(?:, )?)+)\)')
_WITH = re.compile(r'With what "(\w+)": ')
_CHOICE = re.compile(r'^- what "(\w+)": ', re.M)


def _first(text: str, most: int) -> str:
    """Words cut to their first sentence, at most `most` words."""
    first = re.split(r"(?<=\.)\s+(?=[A-Z(`\"])", " ".join(text.split()), maxsplit=1)[0]
    words = first.split()
    return first if len(words) <= most else " ".join(words[:most]).rstrip(",;:") + " …"


def _with_words(v: dict, said: str | None) -> dict:
    return {**{a: b for a, b in v.items() if a != "description"}, **({"description": said} if said else {})}


def shorten(tools: Tools, say: dict, arg: dict, arg_of: dict, most: int = 15) -> Tools:
    """Every tool's short sentence and short argument words, in place (run on the parts, before they are joined)."""
    for name, tool in list(tools._tools.items()):
        props = {}
        for k, v in tool.schema.get("properties", {}).items():
            said = arg_of.get((name, k), arg.get(k))
            props[k] = _with_words(v, _first(v["description"], most) if said is None and v.get("description") else said)
        spec, _ = _schema_of({**tool.schema, "properties": props})
        tools._tools[name] = dataclasses.replace(tool, description=say.get(name, tool.description), schema=spec)
    return tools


def tidy(tools: Tools, names, plain=frozenset()) -> Tools:
    """The joined tools `names` in fewer characters, same information: `what`'s own words short and the choice names
    unquoted ('(for what "a", "b")' -> '(what a, b)'; quotes cost twice in the JSON a client reads). An argument in
    `plain` drops its choice list (a wrong choice is refused by name)."""
    for name in names:
        tool = tools._tools[name]
        props = {}
        for k, v in tool.schema["properties"].items():
            said = v.get("description", "")
            if k == "what":
                said = "Which one (listed above)" + (f'; default {v["default"]}' if "default" in v else "") + "."
            said = _FOR.sub(lambda m: "" if k in plain else "(what " + m[1].replace('"', "") + ")", said)
            props[k] = _with_words(v, _WITH.sub(lambda m: f"what {m[1]}: ", said).strip())
        spec, _ = _schema_of({**tool.schema, "properties": props})
        tools._tools[name] = dataclasses.replace(tool, description=_CHOICE.sub(lambda m: f"- {m[1]}: ", tool.description), schema=spec)
    return tools


def detail_page(tools: Tools, groups, intro: str) -> str:
    """The guide page `tools-in-detail`: every part's full description and argument texts, by the name to call it.
    `groups` is the app's tool_groups.GROUPS ((joined, lead, {choice: part}, default), ...)."""
    where = {part: f'{joined} what "{w}"' for joined, _, parts, _ in groups for w, part in parts.items()}
    out = ["# Every tool in detail", "", intro, ""]
    for name, tool in tools._tools.items():
        out += [f"## {where.get(name, name)}", "", " ".join(tool.description.split()), ""]
        for k, v in tool.schema.get("properties", {}).items():
            kinds = v.get("type") or "/".join(s.get("type", "") for s in v.get("anyOf", []))
            pick = f' One of: {", ".join(map(str, v["enum"]))}.' if v.get("enum") and len(v["enum"]) <= 12 else ""
            out.append(f'- `{k}` ({kinds}): {" ".join(v.get("description", "").split())}{pick}')
        out.append("")
    return "\n".join(out)
