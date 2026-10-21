"""How-to guides: techniques and how tools work, never style rules or finished pieces (AGENTS.md).

Served by `inspect_guide` and as MCP resources `rostrum://guide/<topic>`.
"""
from __future__ import annotations

from pathlib import Path

from ..errors import RostrumError

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

TOOLS_POINTER = "\n\n*Every tool of this server, by verb, with its arguments: call `inspect_tools`.*\n"


class Guides:
    """Topic -> markdown text. Add with `add`, or load a folder of `<topic>.md` files."""

    def __init__(self, topics: dict[str, str] | None = None):
        self._topics = {"start-here": START_HERE, **(topics or {})}

    def add(self, topic: str, text: str):
        self._topics[topic] = text

    def load_folder(self, folder) -> "Guides":
        for f in sorted(Path(folder).glob("*.md")):
            self._topics[f.stem] = f.read_text(encoding="utf-8")
        return self

    def topics(self) -> list[str]:
        return sorted(self._topics)

    def get(self, topic: str) -> str:
        if topic not in self._topics:
            raise RostrumError.not_found("", "guide", topic, self._topics, "the guides of this server")
        text = self._topics[topic]
        if topic == "start-here" and "inspect_tools" not in text:     # every app's start-here points to the tool list
            text = text.rstrip() + TOOLS_POINTER
        return text

    def title(self, topic: str) -> str:
        first = self._topics[topic].lstrip().splitlines()[0] if self._topics[topic].strip() else topic
        return first.lstrip("# ").strip() or topic
