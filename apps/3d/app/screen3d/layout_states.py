"""Rostrum3D's screen states for the layout check (rostrum_gui/layout_run.py): the one workspace with each kind of thing
selected (mesh, group, light, dome, camera, material, shot), the playhead on a key, the viewport's modes, the open
menus and drawers, and the long-text cases (a long item name, a long status message, a failed render line).
The window is SPEC §1's (brief 1): header, rail and flyouts, scene list with its keys, settings panel.
A state is (name, start args, steps). Add one whenever a screen or panel is added; name it in QUICK when it is one of
the most important (the quick check runs those). Every state is the small sample document the screen opens on; none
starts a final render (that is the GPU's heavy job): the render's own lines are `say` states.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from .sample import SOURCE

LONG_NAME = "Hero_product_on_the_marble_plinth_with_the_second_softbox_from_camera_left_and_a_long_rim_strip"
LONG_STATUS = ("Error: render: the picture was not written: the engine said done but wrote no file, "
               "so nothing was shown; check the render folder and try again.")
IGNORE = ()
# The most important states: `main.py --check-layout <folder> --quick` runs just these, at 1646x900 (Sam's screen).
QUICK = ("workspace", "mesh-selected", "light-selected", "camera-selected", "material-selected", "shapes-flyout",
         "lights-flyout", "page-animate", "commands", "guide", "long-name", "long-status", "file-menu", "start-screen", "render-sheet-shot")
BATCH = 6
SCRATCH = tempfile.TemporaryDirectory(prefix="rostrum-layout-")      # removed when the check run ends


def long_names() -> list[str]:
    """Start args for a script that names its box, light and material very long ."""
    script = Path(tempfile.mkdtemp(dir=SCRATCH.name)) / "long_names.py"
    script.write_text(SOURCE.replace('"block"', f'"{LONG_NAME}"').replace('"clay"', f'"{LONG_NAME}_material"')
                      .replace('"key"', f'"{LONG_NAME}_key"'), encoding="utf-8")
    return ["--script", str(script)]


def states() -> list[tuple[str, list[str], list[str]]]:
    s: list[str] = []                       # the plain sample document: no start arguments
    return [
        ("workspace", s, []),
        ("mesh-selected", s, ["select block"]),
        ("mesh-more", s, ["select block", "more"]),
        ("group-selected", s, ["select set"]),
        ("light-selected", s, ["select key"]),
        ("dome-selected", s, ["select sky"]),
        ("camera-selected", s, ["select cam"]),
        ("camera-dof", s, ["select cam", "set dof true"]),
        ("material-selected", s, ["select glass"]),
        ("shot-selected", s, ["select hero"]),
        ("playhead-mid-move", s, ["select cam", "frame 24"]),
        ("key-selected", s, ["select cam", "frame 24", "keydrag cam.x.k2000 36"]),
        ("animating-a-setting", s, ["select vase", "animate y"]),
        ("free-camera", s, ["mode free", "orbit 40 10"]),
        ("lights-off", s, ["lights off", "exposure 1"]),
        ("added-item", s, ["add mesh:sphere"]),
        ("history-longer", s, ["select block"] + [f"set y {0.15 + n / 100}" for n in range(8)]),
        ("shapes-flyout", s, ["rail shapes"]),
        ("lights-flyout", s, ["rail lights"]),
        ("camera-flyout", s, ["rail camera"]),
        ("materials-menu", s, ["materials"]),
        ("shots-menu", s, ["shots"]),
        ("view-menu", s, ["select key", "view"]),
        ("page-animate", s, ["select cam", "page animate"]),
        ("page-render", s, ["page render"]),
        ("file-menu", s, ["file-menu"]),
        ("start-screen", s, ["startscreen open"]),
        ("export-sheet", s, ["export-open"]),
        ("render-sheet", s, ["render-sheet"]),
        ("render-sheet-shot", s, ["page animate", "render-sheet", "estimate-wait"]),
        ("render-sheet-budget", s, ["page animate", "render-sheet", "estimate-wait", "budget 1 s"]),
        ("commands", s, ["commands"]),
        ("commands-search", s, ["commands light"]),
        ("guides-list", s, ["guides open"]),
        ("guide", s, ["guides open agents.md"]),
        ("key-list", s, ["keylist open"]),
        ("panels-folded", s, ["panels fold"]),
        ("long-name", long_names(), [f"select {LONG_NAME}"]),
        ("long-name-light", long_names(), [f"select {LONG_NAME}_key"]),
        ("long-status", s, [f"say {LONG_STATUS}"]),
        ("render-failed-line", s, ["say Error: render: the picture was not written"]),
    ]
