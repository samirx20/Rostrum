"""Version B's guides (ROSTRUM2D_TOOLSET=small): the one shared body in apps/2d/guides, with only the "how do I call
this" lines rewritten from A's tools to B's four (run_script, look, export, read_guide), plus a generated page
`tool-reference` made from the hidden tools' own descriptions and arguments, so A and B carry the same information.
A check is `look {"check": "<A name>", ...}`; a direct change is `run_script {"do": "<A name>", ...}` (small_toolset.DOES).

    python -m rostrum2d.mcp.guides_small <out-folder>      writes every B page as <topic>.md, for reading as files
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from rostrum_core.mcp import Guides
from rostrum_core.mcp.guides import TOOLS_POINTER, split_front

from . import small_toolset

B_TOOLS = ("run_script", "look", "export", "read_guide")
CHECKS, DOES = tuple(small_toolset.CHECKS), tuple(small_toolset.DOES)
HIDDEN = DOES + ("inspect_tools", "inspect_screen", "render_video", "render_export", "inspect_guide")
A_ONLY = CHECKS + HIDDEN
RENAMED = {"render_export": "export", "render_video": "export", "inspect_guide": "read_guide"}
GAPS: list[tuple[str, str, int, str]] = []        # filled by load_b_guides: (A name, guide, line, the line), see gaps()
B_POINTER = ("\n\n*Every check `look` runs, every direct change `run_script` makes with `do`, and every export setting, "
             "with its arguments: read_guide 'tool-reference'.*\n")

_C, _D = "|".join(CHECKS), "|".join(DOES)
# Whole phrases whose B form is not a plain rename (regex, with any run of spaces/newlines as \s+).
PHRASES = [
    (r"`run_open_project \{\"folder\": ", "`run_script {\"project\": "),
    (r"`\{\"folder\": \"\.\.\.\", \"item\"", "`{\"project\": \"...\", \"item\""),
]
PHRASES = [(re.compile(p.replace(" ", r"\s+")), b) for p, b in PHRASES]
SOUND = re.compile(r"\(its `run_open_project`\)|`run_open_project` on the same folder")    # RostrumSound's own tool: B has it too
CALL = re.compile(rf"\b({_C}|{_D}|render_video)(\s+)\{{(\s*)(\}}|\"|[a-z])")   # NAME {args} -> look {"check": NAME, args}
BARE_ARGS = re.compile(rf"`({_C}) ([^`{{][^`]*)`")                                # `inspect_operations name: key.add`
BARE_WHAT = re.compile(rf"`({_C})` \(`what: (\"[^\"]+\")`\)")                     # `look_frame` (`what: "sheet"`)
BARE = re.compile(rf"(?<!check )(?<!do )`({_C}|{_D})`")
PLAIN = re.compile(rf"(?<![\w\"`])(?<!check )(?<!do )({_C}|{_D})(?: \(what: (\w+)\))?(?![\w\"`])")   # a description's prose
ALLOWED = re.compile(rf"\"(?:check|do)\": \"(?:{_C}|{_D})\"|(?:check|do): \"(?:{_C}|{_D})\"|(?:check|do) `?(?:{_C}|{_D})")


def _call(m) -> str:
    name, space, pad, nxt = m.groups()
    tool, key = ("export", "format") if name == "render_video" else ("run_script", "do") if name in DOES else ("look", "check")
    value = "mp4" if name == "render_video" else name
    key = f'"{key}"' if nxt in '"}' else key
    return f'{tool}{space}{{{pad}{key}: "{value}"' + ("}" if nxt == "}" else ", " + nxt)


def _bare(name: str, beats: bool) -> str:
    if name in DOES:
        return f"`run_script` (do `{name}`)"
    return f"`look` check `{name}`"


def _plain(m, beats: bool) -> str:
    if m[1] in DOES:
        return f"run_script (do {m[1]})"
    return f"look (check {m[1]}{f', what: {m[2]}' if m[2] else ''})"


def b_text(markdown: str) -> str:
    """A guide's text with A's call lines in B form. Mechanical: the same words, other tool names. Plain `look` gives
    the review without beats, so a line that gives beats keeps the review as its check."""
    kept: list[str] = []
    text = SOUND.sub(lambda m: kept.append(m[0]) or f"\0{len(kept) - 1}\0", markdown)
    for pattern, b in PHRASES:
        text = pattern.sub(b, text)
    text = CALL.sub(_call, text)
    text = BARE_ARGS.sub(lambda m: f"`look` check `{m[1]}` with `{m[2]}`", text)
    text = BARE_WHAT.sub(lambda m: f'`look` (`check: "{m[1]}"`, `what: {m[2]}`)', text)
    lines = []
    for line in text.split("\n"):
        beats = "beats" in line
        line = BARE.sub(lambda m: _bare(m[1], beats), line)
        lines.append(PLAIN.sub(lambda m: _plain(m, beats), line))
    text = "\n".join(lines)
    for a, b in RENAMED.items():
        text = re.sub(rf"\b{a}\b", b, text)
    for dup in ("`export` and `export`", "`export` / `export`", "`export`, `export`"):
        text = text.replace(dup, "`export`")
    text = text.replace(" (or `export`)", "").replace("(or `export`)", "")
    return re.sub(r"\0(\d+)\0", lambda m: kept[int(m[1])], text)


def leftovers(text: str) -> list[tuple[int, str, str]]:
    """(line, A name, the line) for every A-only tool name still in a B page, outside a check's or a do's name."""
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        rest = SOUND.sub("", ALLOWED.sub("", line))
        out += [(n, name, line.strip()) for name in re.findall(rf"\b({'|'.join(A_ONLY)})\b", rest)]
    return out


def _arg_lines(schema: dict) -> list[str]:
    props, need = (schema or {}).get("properties", {}), set((schema or {}).get("required", []))
    rows = []
    for key, p in props.items():
        kind = "/".join(map(str, p["enum"])) if "enum" in p and len(p["enum"]) <= 8 else p.get("type", "")
        rows.append(f"- `{key}`{' (required)' if key in need else ''}{f' ({kind})' if kind else ''}: {b_text(p.get('description', ''))}")
    return rows


def _section(head: str, tool) -> list[str]:
    return [f"## {head}\n", b_text(tool.description).strip() + "\n", *_arg_lines(tool.schema), ""]


def tool_reference(tools) -> str:
    """The page `tool-reference`: each hidden check as a B `look` call, each direct change as a `run_script` do call,
    then export's and run_script's arguments, in A's own words (descriptions and argument schemas): B knows what A knows."""
    by_name = {t.name: t for t in (tools.all() if hasattr(tools, "all") else tools)}
    out = ["# Tool reference: every check of `look`, every `do` of `run_script`, `export` and `run_script`\n",
           "`look` with no `check` gives a contact sheet and the film's weakest moments. With `check` it runs one of "
           "the checks below with that check's own arguments, e.g. `look {\"check\": \"look_motion\", \"what\": \"curve\", "
           "\"id\": \"title\", \"field\": \"y\"}`. `run_script` with `do` (and no script) makes one direct change with "
           "that change's own arguments, e.g. `run_script {\"do\": \"edit_markers\", \"ops\": [...]}`.\n"]
    out += [line for n in CHECKS if n in by_name for line in _section(f'look {{"check": "{n}"}}', by_name[n])]
    out += [line for n in DOES if n in by_name for line in _section(f'run_script {{"do": "{n}"}}', by_name[n])]
    out += [line for a, b in (("render_export", "export"), ("run_script", "run_script")) if a in by_name
            for line in _section(b, by_name[a])]
    return "\n".join(out)


class BGuides(Guides):
    """Guides whose start-here points to the B tool reference instead of A's tool list."""

    def get(self, topic: str) -> str:
        text = super().get(topic)
        return text.replace(TOOLS_POINTER, B_POINTER) if topic == "start-here" else text


def load_b_guides(folder, tools=None) -> Guides:
    """Like Guides().load_folder(folder), every page through b_text, plus `tool-reference` when `tools` is given."""
    guides = BGuides()
    for f in sorted(Path(folder).glob("*.md")):
        guides.add(f.stem, b_text(split_front(f.read_text(encoding="utf-8"))[1]))
    if tools is not None:
        guides.add("tool-reference", tool_reference(tools))
    GAPS[:] = gaps(guides)
    return guides


def gaps(guides: Guides) -> list[tuple[str, str, int, str]]:
    """(A name, guide, line, the line) still left in B's pages: a call line the rewrite does not know. Empty when B's
    guides name only B's tools (check and do names aside)."""
    return [(name, topic, n, line) for topic in guides.topics() for n, name, line in leftovers(guides.get(topic))]


def full_tools():
    """Version A's whole tool set, which the B server keeps behind its four (ROSTRUM2D_TOOLSET unset)."""
    import os
    os.environ.pop("ROSTRUM2D_TOOLSET", None)
    from .server import make_app, make_runtime
    return make_runtime(make_app(None)).tools


def write_b_folder(out, tools) -> list[Path]:
    """Every B page as <topic>.md in `out` (made if missing), for agents that read the guides as files."""
    from .server import GUIDES
    guides, out = load_b_guides(GUIDES, tools), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    files = []
    for topic in guides.topics():
        files.append(out / f"{topic}.md")
        files[-1].write_text(guides.get(topic), encoding="utf-8")
    return files


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m rostrum2d.mcp.guides_small <out-folder>")
    written = write_b_folder(sys.argv[1], full_tools())
    print(f"{len(written)} pages in {Path(sys.argv[1]).resolve()}; leftover A names: {len(GAPS)}")
    for name, topic, n, line in GAPS:
        print(f"  {topic}:{n} {name}: {line[:120]}")
