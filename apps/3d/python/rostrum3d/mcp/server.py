"""The `rostrum-3d` MCP server.

    python -m rostrum3d.mcp --project <folder> --item <id> [--item <id> ...]      (stdio; opens or creates each item)
    rostrum-3d --project <folder> --item <id>                                     (the same, as an installed command)

Every change is saved at once, so the 3D screen process can open the same file. Tools: the shared ones from rostrum_core, plus
look_frame, look_sheet, look_at, render_still, render_video, render_estimate, inspect_usd_file, inspect_shot. One engine process (`rostrum3d-core
serve`) is started on first use and kept for the session.
"""
from __future__ import annotations

import argparse
import atexit
from dataclasses import dataclass
from pathlib import Path

from rostrum_core import Document
from rostrum_core.mcp import App, Guides, run_stdio
from rostrum_core.storage import paths

from rostrum3d.engine import Engine
from rostrum3d.kind import KIND
from rostrum3d.script import run_source
from . import estimate, facts, look, render

GUIDES = Path(__file__).resolve().parents[1] / "guides"
INSTRUCTIONS = ("rostrum-3d makes 3D shots: a scene of meshes, imports, lights and cameras, animated by keys and rendered by Hydra "
                "(Storm for quick looks, Cycles for the final picture). Read inspect_guide 'agents', build with run_script, then check "
                "your work through the shot's camera with look_frame, look_sheet and look_at before any render_still or render_video.")


@dataclass
class ThreeDState:
    engine: Engine


def app_tools():
    return look.tools.merged_with(render.tools).merged_with(facts.tools).merged_with(estimate.tools)


def open_documents(project: str, items: list[str]) -> dict:
    """Open each item from the project folder (or start it empty when it has no file yet), saving after every change."""
    docs = {}
    for item in items:
        exists = paths(project, item, KIND.ext)["doc"].exists()
        doc = Document.open(project, item, KIND) if exists else Document.new(KIND, project, item)
        doc.subscribe(lambda ev, d=doc: d.save() if ev.kind == "change" else None)
        if not exists:
            doc.save()
        docs[item] = doc
    return docs


def make_app(project: str | None = None, items: list[str] | None = None, documents: dict | None = None, engine: Engine | None = None) -> App:
    docs = documents if documents is not None else open_documents(project, items or [])
    app = App("rostrum-3d", docs, run_source=run_source, instructions=INSTRUCTIONS, guides=Guides().load_folder(GUIDES), folder=project)
    app.state = ThreeDState(engine or Engine())          # the process starts on the first request, not now
    atexit.register(app.state.engine.close)
    return app


def main(argv=None):
    ap = argparse.ArgumentParser(prog="rostrum-3d", description="The rostrum-3d MCP server (stdio).")
    ap.add_argument("--project", required=True, help="The project folder.")
    ap.add_argument("--item", action="append", required=True, help="A document's item id (repeat for several).")
    a = ap.parse_args(argv)
    run_stdio(make_app(a.project, a.item), app_tools())


if __name__ == "__main__":
    main()
