"""The 3D server's tools, few and clear (CONVENTIONS § 2): tools that answer the same kind of question are one tool, and
`what` picks the question. Each part is still written as its own small tool in its own module; this list joins them.
An old name answers with an error naming the tool and the `what` to pass (rostrum_core.mcp.combine)."""
from __future__ import annotations

from rostrum_core.mcp.combine import combine

GROUPS = [
    ("look_frame", "See the shot through its camera (`width`: the picture's width in px). Checked looks open NOT DONE: "
     "(dark, cut, floating, apart, leaving, no floor) or DONE:.",
     {"frame": "look_frame", "sheet": "look_sheet", "shots": "look_shots", "material": "look_material",
      "shape": "look_shape", "paint": "look_paint", "coverage": "look_coverage", "where": "look_where",
      "exposure": "inspect_exposure"}, "frame"),
    ("edit_place_on", "Place by a pixel (x, y) of the shot's picture (`width` as look_frame gave it). One undo step; then look_frame. "
     "Guide 'getting-started' (Eyes).",
     {"mesh": "edit_place_on", "highlight": "edit_place_highlight"}, "mesh"),
    ("edit_import_asset", "Free CC0 models from the asset library's sources (Poly Haven, ambientCG). Guide 'agents' (Asset library).",
     {"import": "edit_import_asset", "search": "inspect_assets", "sources": "inspect_asset_sources"}, "import"),
    ("run_simulation", "A shot's simulation: things set to Falls drop and rest on Stays still things and the ground, Cloth "
     "drapes (set up with sim.body / sim.set). Stored until something it depends on changes. Guide 'simulate'.",
     {"run": "run_simulation", "status": "inspect_simulation"}, "run"),
]

CORE = ["run_script", "look_frame", "edit_place_on", "inspect_guide", "render_still"]


def group(tools):
    """Join the parts in place and name the core five; returns `tools`."""
    for name, lead, parts, default in GROUPS:
        combine(tools, name, lead, parts, default=default)
    tools.core = list(CORE)
    return tools
