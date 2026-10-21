"""The `rostrum-sound` app as the MCP server sees it: the open Sound documents (saved after every change),
the one engine process, and where renders and looks are written.

Renders are the item's versions, `<project folder>/renders/<item>/vNNN/` (mix, stems, manifest: handoff.py); a solo /
mute listening check goes to `.../check/`, look pictures to `.../look/`. The last render of each item is remembered
(`renders/<item>/last.json`, so it survives a restart), and look tools default to it.
"""
from __future__ import annotations

import atexit
import json
from dataclasses import dataclass
from pathlib import Path

from rostrum_core import Document, RostrumError, codes
from rostrum_core.mcp import App, Guides

from ..doc import KIND, markers
from ..engine import Engine
from ..script import run_source

GUIDES = Path(__file__).resolve().parents[3] / "guides"         # apps/sound/guides
INSTRUCTIONS = ("rostrum-sound makes music, effects and mixes. A Sound document holds tracks (an instrument, notes, "
                "drum hits, recorded clips), effects, automation, markers and the master. Write with run_script (the "
                "Python script API in inspect_guide 'script'), adjust with edit_document, render with render_mix, then "
                "listen with the look_* tools. A voice track speaks lines: add them with line.add, make their audio "
                "with render_voice, then render.")


@dataclass
class SoundState:
    folder: Path
    engine: Engine

    def renders(self, item: str) -> Path:
        return self.folder / "renders" / item

    def look_dir(self, item: str) -> Path:
        d = self.renders(item) / "look"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def remember(self, item: str, result: dict):
        (self.renders(item) / "last.json").write_text(json.dumps(result), encoding="utf-8")

    def last_render(self, item: str, where: str) -> dict:
        f = self.renders(item) / "last.json"
        if not f.is_file():
            raise RostrumError(codes.NOT_FOUND, where, f'"{item}"', "has no render yet", hint="Call render_mix first, or pass wav=<path>.")
        return json.loads(f.read_text(encoding="utf-8"))


def open_or_new(folder: Path, item: str) -> Document:
    doc_file = folder / "docs" / f"{item}{KIND.ext}"
    doc = Document.open(folder, item, KIND) if doc_file.is_file() else Document.new(KIND, folder=folder, item=item)
    doc.save()
    doc.subscribe(lambda ev: doc.save())             # every change is on disk at once
    return doc


def make_app(folder: str | Path, items: list[str]) -> App:
    folder = Path(folder).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    markers.use_project(folder)                      # every marker read sees this project's shared markers
    engine = Engine()
    atexit.register(engine.close)
    app = App("rostrum-sound", {i: open_or_new(folder, i) for i in items}, run_source=run_source,
              instructions=INSTRUCTIONS, guides=Guides().load_folder(GUIDES), folder=str(folder))
    app.state = SoundState(folder, engine)
    return app
