"""The `rostrum-2d` MCP server.

    python -m rostrum2d.mcp --project <folder> --item <id> [--item <id> ...]     (stdio; opens or creates each item)

Every change is saved at once, so the 2D screen process can open the same file. Tools: the shared ones from
rostrum_core, plus look_frame, look_sheet, look_motion, look_at, render_video.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from rostrum_core import Document
from rostrum_core.mcp import App, Guides, run_stdio
from rostrum_core.storage import paths

from rostrum2d import KIND, run_source
from . import at, curves, draw, look, motion, rig, video
from . import lipsync

SKILLS = Path(__file__).resolve().parents[3] / "skills"
INSTRUCTIONS = ("rostrum-2d makes motion graphics: compositions of shape / text / image / group layers animated by keys. "
                "Read inspect_guide 'start-here', build with run_script, then check your work with look_frame, look_sheet and look_motion. "
                "Draw on drawing layers with stroke.add calls (one call list = one undo step) and check with look_drawing, "
                "inspect_drawing_at and inspect_stroke_landed; read inspect_guide 'drawing'.")


def app_tools():
    return (look.tools.merged_with(motion.tools).merged_with(at.tools).merged_with(video.tools)
            .merged_with(draw.tools).merged_with(rig.tools).merged_with(lipsync.tools).merged_with(curves.tools))


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


def make_app(project: str | None = None, items: list[str] | None = None, documents: dict | None = None) -> App:
    docs = documents if documents is not None else open_documents(project, items or [])
    return App("rostrum-2d", docs, run_source=run_source, instructions=INSTRUCTIONS, guides=Guides().load_folder(SKILLS),
               folder=project)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="rostrum2d.mcp", description="The rostrum-2d MCP server (stdio).")
    ap.add_argument("--project", required=True, help="The project folder.")
    ap.add_argument("--item", action="append", required=True, help="A document's item id (repeat for several).")
    a = ap.parse_args(argv)
    run_stdio(make_app(a.project, a.item), app_tools())


if __name__ == "__main__":
    main()
