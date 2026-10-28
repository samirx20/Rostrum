"""How-to guides: techniques and how tools work, never style rules or finished pieces (AGENTS.md).

Served by `inspect_guide` and as MCP resources `rostrum://guide/<topic>`.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..errors import RostrumError, codes

URI = "rostrum://guide/"

START_HERE = """# Start here: how every Rostrum server answers

- Every reply has `ok`, `summary` (read it first), `data`, `files` (absolute paths) and `warnings`. A failure has `ok: false`
  and an `error` with `code`, `where`, `problem`, `accepted` and a hint. Read `accepted`: it lists what would have worked.
- Tool names are `<verb>_<thing>`: `inspect_*` reads, `edit_*` and `run_*` change the document through operations,
  `render_*` makes files as a job, `look_*` lets you see or hear a result.
- `inspect_operations` lists every operation and its arguments. `edit_document` applies a list of them, all or nothing.
- Your changes carry your client name and are grouped per turn, so a person can review or undo them together.
- `run_script` merges what the script makes into the document. Anything a person moved by hand stays where they put it
  and is listed in the reply as held back; pass `force` with those keys only when you mean to overwrite.
- Long work comes back as a job id. Ask with `inspect_job` (`wait_s` up to 25); stop with `run_stop`.
"""

CAP = 8000      # characters of a guide one inspect_guide reply carries before it lists the remaining sections


def split_front(text: str) -> tuple[dict, str]:
    """A guide's front matter and the rest. Front matter is an optional first block of `key: value` lines between two
    `---` lines (the Help menu reads `help:` and `order:` from it); a guide without one comes back whole."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            meta = {}
            for row in lines[1:i]:
                key, sep, value = row.partition(":")
                if sep:
                    meta[key.strip()] = value.strip()
            return meta, "".join(lines[i + 1:]).lstrip(chr(10))
    return {}, text


def _head(part: str) -> str:
    return part.splitlines()[0].lstrip("# ").strip()


TOOLS_POINTER ="\n\n*Every tool of this server, by verb, with its arguments: call `inspect_tools`.*\n"


class Guides:
    """Topic -> markdown text. Add with `add`, or load a folder of `<topic>.md` files."""

    def __init__(self, topics: dict[str, str] | None = None):
        self._topics = {"start-here": START_HERE, **(topics or {})}
        self._origins: dict[str, str] = {}      # topic -> a plugin's id; a built-in guide has no entry

    def add(self, topic: str, text: str, origin: str = "builtin"):
        self._topics[topic] = text
        self._origins[topic] = origin

    def load_folder(self, folder, origin: str = "builtin") -> "Guides":
        for f in sorted(Path(folder).glob("*.md")):
            self.add(f.stem, split_front(f.read_text(encoding="utf-8"))[1], origin)
        return self

    def origin(self, topic: str) -> str:
        return self._origins.get(topic, "builtin")

    def topics(self) -> list[str]:
        return sorted(self._topics)

    def get(self, topic: str) -> str:
        if topic not in self._topics:
            raise RostrumError.not_found("", "guide", topic, self._topics, "the guides of this server")
        text = self._topics[topic]
        if topic == "start-here" and "inspect_tools" not in text:     # every app's start-here points to the tool list
            text = text.rstrip() + TOOLS_POINTER
        return text

    def part(self, topic: str, section: str | None = None, cap: int = CAP) -> str:
        """The guide cut to fit a reply: `section` (words of a `## ` heading; "all" = whole) gives that section; with
        none, start-here whole and any other guide's sections up to `cap` characters, then the rest's headings."""
        text = self.get(topic)
        parts = re.split(r"(?m)^(?=## )", text)
        if section == "all" or (section is None and (topic == "start-here" or len(text) <= cap)):
            return text
        if section is not None:
            want = section.lower().lstrip("# ").strip()
            hits = [p for p in parts[1:] if want in p.splitlines()[0].lower()]
            if not hits and want in self._topics:
                raise RostrumError(codes.NOT_FOUND, "inspect_guide", f'"{section}"', f'no section "{section}" in the guide "{topic}"',
                                   [_head(p) for p in parts[1:]], f'"{want}" is a guide of its own: inspect_guide topic "{want}"')
            if not hits:
                raise RostrumError.not_found("inspect_guide", "section", section, [_head(p) for p in parts[1:]], f'the guide "{topic}"')
            return "".join(hits)
        out, n = [], 0
        while n < len(parts) and (not out or sum(map(len, out)) + len(parts[n]) <= cap):
            out.append(parts[n])
            n += 1
        rest = [_head(p) for p in parts[n:]]
        return "".join(out).rstrip() + (f"\n\n*{len(rest)} more section{'s' * (len(rest) != 1)}: " + "; ".join(rest) +
                                        '. Ask with `section` (words of its heading), or section: "all".*\n' if rest else "")

    def title(self, topic: str) -> str:
        first = self._topics[topic].lstrip().splitlines()[0] if self._topics[topic].strip() else topic
        return first.lstrip("# ").strip() or topic
