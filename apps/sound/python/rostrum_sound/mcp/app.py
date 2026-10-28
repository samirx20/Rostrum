"""The `rostrum-sound` app as the MCP server sees it: the open Sound documents (saved after every change),
the one engine process, and where renders and looks are written.

Renders are the item's versions, `<project folder>/renders/<item>/vNNN/` (mix, stems, manifest: handoff.py); a solo /
mute listening check goes to `.../check/`; look pictures go to `<project folder>/looks/<item>/` (rostrum_core's
`look_folder`, the one place every app's look pictures go). The last render of each item is remembered
(`renders/<item>/last.json`, so it survives a restart), and look tools default to it.
"""
from __future__ import annotations

import atexit
import json
from dataclasses import dataclass
from pathlib import Path

from rostrum_core import Document, RostrumError, codes, live
from rostrum_core.mcp import App, Guides
from rostrum_core.mcp.files import look_folder

from .. import opening
from ..doc import KIND, markers
from ..engine import Engine
from ..script import run_source
from . import script_render

GUIDES = Path(__file__).resolve().parents[3] / "guides"         # apps/sound/guides
INSTRUCTIONS = ("rostrum-sound makes music, effects and mixes. A Sound document holds tracks (an instrument, notes, "
                "drum hits, recorded clips), effects, automation, markers and the master. Before composing, read inspect_guide 'writing-music' "
                "and 'start-here'. THE LOOP: write the whole piece as ONE Python script (tempo map, sections, markers for the sync points, every "
                "track's notes, dynamics, effects, the mix and the master target; names in inspect_guide 'script'), run it with run_script under "
                "one name with look: true (it renders and listens), read the listening check in the reply, edit the script and run it again under the same name "
                "(a removed track, note or marker disappears; a new name that re-makes the same tracks is refused). "
                "Make an asked moment read with moment(name, at) in the script (rest before it, stop the band, strike its layers; inspect_guide 'script' › Moments that read). "
                "A delivery (render_mix, or look with folder) is refused while a fault is open unless keep: {id: why} explains it; the brief's own moment is kept only after a render that tried the fix, with a measured number in the reason. "
                "Use edit_document only for one-off touch-ups. "
                "Check with look_arrangement (a picture, and which tracks start on each marker), look_sound (loudness, levels, spectrum, stereo, "
                "low end, clashes) and look_music (onsets, beats, pitch, harmony). A voice track speaks lines: add them with line.add, make their audio "
                "with render_voice, then render. The server starts on your own song: the one you last opened from this folder (a resumed session gets it back), else a fresh scratch project made for you, never the person's work (the first reply says which); "
                "the person's songs open only when you ask: run_open_project lists them (what \"recent\") and switches. Every reply ends with a clock line (time since your first call; the minutes left when you have a budget); a finished render asks for a fix pass: listen, name the three weakest moments, change the script, run it again.")


NO_PROJECT = "No project is open. Open one in RostrumSound, or call run_open_project with a folder."


@dataclass
class SoundState:
    folder: Path | None            # None: no project is open
    engine: Engine

    def renders(self, item: str) -> Path:
        return self.folder / "renders" / item

    def look_dir(self, item: str) -> Path:
        return look_folder(self.folder, item)

    def remember(self, item: str, result: dict):
        (self.renders(item) / "last.json").write_text(json.dumps(result), encoding="utf-8")

    def last_render(self, item: str, where: str) -> dict:
        f = self.renders(item) / "last.json"
        if not f.is_file():
            raise RostrumError(codes.NOT_FOUND, where, f'"{item}"', "has no render yet", hint="Call render_mix first, or pass wav=<path>.")
        return json.loads(f.read_text(encoding="utf-8"))


def open_or_new(folder: Path, item: str) -> Document:
    doc_file = folder / "docs" / f"{item}{KIND.ext}"
    doc = opening.open_whole(folder, item) if doc_file.is_file() else Document.new(KIND, folder=folder, item=item)
    live.keep(doc)                                   # every change is on disk at once, through the one shared door
    return doc


def open_project(app: App, folder: str | Path | None, items: list[str]) -> None:
    """Make `folder` / `items` the app's open songs, as at start-up: the one engine process stays; markers and renders
    follow the folder. Nothing open when there is no folder."""
    folder = Path(folder).resolve() if folder else None
    if folder:
        folder.mkdir(parents=True, exist_ok=True)
    markers.use_project(folder)                      # every marker read sees this project's shared markers
    app.documents = {i: open_or_new(folder, i) for i in items} if folder else {}
    app.folder = str(folder) if folder else None
    app.state.folder = folder


def make_app(folder: str | Path | None = None, items: list[str] | None = None) -> App:
    engine = Engine()
    atexit.register(engine.close)
    instructions = INSTRUCTIONS if folder else f"{INSTRUCTIONS} {NO_PROJECT}"
    app = App("rostrum-sound", {}, run_source=run_source, instructions=instructions, guides=Guides().load_folder(GUIDES),
              script_look=script_render.after_run)
    app.state = SoundState(None, engine)
    open_project(app, folder, items or [])
    return app
