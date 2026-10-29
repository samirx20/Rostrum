"""Rostrum3D's screen states for the layout check (rostrum_gui/layout_run.py): the one workspace with each kind of thing
selected (mesh, group, light, dome, camera, material, shot), the playhead on a key, the viewport's modes, the open
menus and drawers, and the long-text cases (a long item name, a long status message, a failed render line).
The window is SPEC §1's (brief 1): header, rail and flyouts, scene list with its keys, settings panel.
A state is (name, start args, steps). Add one whenever a screen or panel is added; name it in QUICK when it is one of
the most important (the quick check runs those). Every state is the small sample document the screen opens on; none
starts a final render (that is the GPU's heavy job): the render's own lines are `say` states.
"""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

from .sample import SOURCE

LONG_NAME = "Hero_product_on_the_marble_plinth_with_the_second_softbox_from_camera_left_and_a_long_rim_strip"
LONG_STATUS = ("Error: render: the picture was not written: the engine said done but wrote no file, "
               "so nothing was shown; check the render folder and try again.")
IGNORE = ()
# The most important states: `main.py --check-layout <folder> --quick` runs just these, at 1646x900 (Sam's screen).
QUICK = ("workspace", "nothing-selected", "mesh-selected", "light-selected", "camera-selected", "material-selected", "material-picker", "material-picker-low", "material-shared", "blocks-view", "blocks-add-list", "shapes-flyout",
         "lights-flyout", "camera-flyout", "rig-selected", "page-animate", "animate-stretch", "animate-poses", "animate-poses-onion", "animate-key-ease", "animate-curves", "animate-curves-picked", "animate-onion", "commands", "guide", "two-solids", "combine-selected", "long-name", "long-status", "file-menu", "start-screen", "context-item", "mesh-edit-faces", "mesh-edit-bevel", "mesh-edit-knife", "paint-layers", "paint-view-coverage", "clay-tool", "clay-brush", "clay-brush-more", "clay-mask", "clay-drawn", "clay-layers", "clay-turn-into", "pose-tool",
         "render-sheet-shot", "render-sheet-exr", "bevel-too-big", "lens-menu", "take-view-hover", "shots-frame", "shot-only-light", "collections-row", "anim-layers-two", "page-render", "render-queue-two", "render-queue-finished", "render-running", "render-done", "clay-selected",
         "import-menu", "import-unit-note", "copies-selected", "copies-context-shape", "copies-scatter-menu", "copies-near-added",
         "sim-not-computed", "sim-filling", "sim-stored", "sim-out-of-date", "sim-failed", "sim-stylize", "sim-render-sheet", "sim-context", "sim-body-selected")
BATCH = 6
SCRATCH = tempfile.TemporaryDirectory(prefix="rostrum-layout-")      # removed when the check run ends


def long_names() -> list[str]:
    """Start args for a script that names its box, light and material very long ."""
    script = Path(tempfile.mkdtemp(dir=SCRATCH.name)) / "long_names.py"
    script.write_text(SOURCE.replace('"block"', f'"{LONG_NAME}"').replace('"clay"', f'"{LONG_NAME}_material"')
                      .replace('"key"', f'"{LONG_NAME}_key"'), encoding="utf-8")
    return ["--script", str(script)]


def two_shots() -> list[str]:
    """Start args for the sample with a second shot through a second camera ("Hero 01", "Close 02")."""
    script = Path(tempfile.mkdtemp(dir=SCRATCH.name)) / "two_shots.py"
    script.write_text(SOURCE.replace('shot("hero", ', 'shot("hero", name="Hero 01", ') +
                      'close = camera("close_cam", focalLength=105, x=0.5, y=0.45, z=1.6).aim((0, 0.3, 0))\n'
                      'shot("close", name="Close 02", camera=close, fps=24, start=0, end=2)\n', encoding="utf-8")
    return ["--script", str(script)]


def lid_turn() -> list[str]:
    """Start args for the sample with a lid on the block that opens: Turn X 0 → −105° from 0.8 s to 1.6 s (mockup 07)."""
    script = Path(tempfile.mkdtemp(dir=SCRATCH.name)) / "lid_turn.py"
    script.write_text(SOURCE + 'mesh("lid", shape="box", width=0.5, height=0.04, depth=0.5, y=0.3, material=clay)'
                      '.key("rx", {0.8: 0, 1.6: -105})\n', encoding="utf-8")
    return ["--script", str(script)]


def mouth_group() -> list[str]:
    """Start args for the sample with a mouth: a group of three flat shapes named as mouth shapes (Lip sync…)."""
    script = Path(tempfile.mkdtemp(dir=SCRATCH.name)) / "mouth_group.py"
    lines = ["with group('mouth', y=0.5):", "    mesh('mouth_rest', shape='disc', radius=0.05)",
             "    mesh('mouth_closed', shape='disc', radius=0.04)", "    mesh('mouth_wide', shape='disc', radius=0.07)"]
    script.write_text(SOURCE + "\n".join(lines) + "\n", encoding="utf-8")
    return ["--script", str(script)]


def drawn_clay() -> list[str]:
    """Start args for the sample with a clay drawn from an outline (CL3), an arm joined to it by a second drawing."""
    script = Path(tempfile.mkdtemp(dir=SCRATCH.name)) / "drawn_clay.py"
    source = re.sub(r'(?<!")\bclay\b(?!")', "clay_mat", SOURCE)     # the sample's material is called clay
    script.write_text(source + 'buddy = clay("buddy", draw=[(0.5, 0, 0.3), (0.62, 0, 0.3), (0.66, 0.12, 0.3), '
                      '(0.6, 0.24, 0.3), (0.52, 0.24, 0.3), (0.46, 0.12, 0.3)], facing=(0, 0, 1))\n'
                      'buddy.draw([(0.04, 0.14, 0), (0.12, 0.17, 0), (0.12, 0.2, 0), (0.04, 0.19, 0)], name="arm")\n',
                      encoding="utf-8")
    return ["--script", str(script)]


TOY_USDA = """#usda 1.0
(
    defaultPrim = "Toy"
    metersPerUnit = 0.01
    upAxis = "Y"
)
def Xform "Toy"
{
    def Cube "Body"
    {
        double size = 20
    }
    def Sphere "Head"
    {
        double radius = 8
        double3 xformOp:translate = (0, 18, 0)
        uniform token[] xformOpOrder = ["xformOp:translate"]
    }
}
"""


def toy_import(*then: str) -> list[str]:
    """Steps that bring in a small file in centimetres (a body and a head: two parts) the way the Import group does, then
    `then`. A script runs before the window and its engine exist, so only this path reads the file's unit and parts."""
    folder = Path(tempfile.mkdtemp(dir=SCRATCH.name))
    (folder / "toy.usda").write_text(TOY_USDA, encoding="utf-8")
    return [f"import-file {folder / 'toy.usda'}", "wait 1500", *then]


def buds(layout: str = "line") -> list[str]:
    """Start args for the sample with a bud (a small sphere) made many times: twelve in a line, or scattered over the block."""
    script = Path(tempfile.mkdtemp(dir=SCRATCH.name)) / f"buds_{layout}.py"
    where = ('layout="line", count=12, spacingX=0.09' if layout == "line"
             else 'layout="surface", surface="block", count=400, minSpacing=0.02, seed=3')
    bud = 'bud = mesh("bud", shape="sphere", radius=0.03, x=-0.5, z=0.7, material=clay)'
    script.write_text(f"{SOURCE}{bud}\ncopies(\"buds\", source=bud, {where})\n", encoding="utf-8")
    return ["--script", str(script)]


def drop() -> list[str]:
    """Start args for the sample with twelve buds that fall (a copies item set to Falls) and the ground plane set to Stays still
    (brief 25): the Simulate row, the bodies' badges, the Scene panel's Simulation group."""
    script = Path(tempfile.mkdtemp(dir=SCRATCH.name)) / "drop.py"
    bud = 'bud = mesh("bud", shape="sphere", radius=0.03, x=-0.5, y=0.57, z=0, material=clay)'
    source = SOURCE.replace('mesh("ground", ', 'mesh("ground", simulate="still", ')
    script.write_text(f'{source}{bud}\ncopies("buds", source=bud, layout="line", count=12, spacingX=0.09, simulate="falls")\n',
                      encoding="utf-8")
    return ["--script", str(script)]


def states() -> list[tuple[str, list[str], list[str]]]:
    s: list[str] = []                       # the plain sample document: no start arguments
    return [
        ("workspace", s, []),
        ("nothing-selected", s, ["deselect"]),
        ("nothing-selected-free", s, ["deselect", "mode free"]),
        ("mesh-selected", s, ["select block"]),
        ("mesh-more", s, ["select block", "more"]),
        ("group-selected", s, ["select set"]),
        ("two-solids", s, ["selectmany block vase"]),
        ("two-solids-hover", s, ["selectmany block vase", "preview combine:subtract", "wait 600"]),
        ("combine-selected", s, ["selectmany block vase", "action combine:subtract"]),
        ("combine-folded", s, ["selectmany block vase", "action combine:union", "fold combine_1"]),
        ("light-selected", s, ["select key"]),
        ("light-final-only", s, ["select key", "set spread 60", "set lightsOnly block"]),   # the Final badges
        ("lipsync-sheet", mouth_group(), ["lipsync mouth"]),                            # Lip sync… on a mouth group (the kit's sheet)
        ("assets-off", s, ["assets"]),                                                  # Import › Asset library: every source off
        ("assets-list", s, ["assets sample", "wait 300"]),                              # Poly Haven on, a fixed offline list (no network)
        ("context-light", s, ["context key"]),                                          # Pick what it lights
        ("dome-selected", s, ["select sky"]),
        ("camera-selected", s, ["select cam"]),
        ("camera-dof", s, ["select cam", "set dof true"]),
        ("material-selected", s, ["select glass"]),
        ("material-picker", s, ["select block", "picker", "wait 300"]),
        # the Material row low in a long panel (an eye: Rotation and Follow open above it, 3D sweep M1): the picker opens
        # upward with its whole list, never squeezed under the row at the window's bottom (the check's `cramped`)
        ("material-picker-low", s, ["add mesh:sphere", "set rx 59.56", "set rz -87.18", "set follow block",
                                    "picker", "wait 300"]),
        ("material-shared", s, ["select vase", "assign clay"]),
        ("material-started", s, ["select block", "startfrom matte plastic"]),
        ("blocks-view", s, ["select glass", "wait 500", "click Edit as blocks", "wait 400"]),              # the bottom panel's block view
        ("blocks-add-list", s, ["select glass", "wait 500", "click Edit as blocks", "wait 400", "click + Add block", "wait 300"]),
        ("blocks-lines-on", s, ["select glass", "set lines true", "wait 500", "click Edit as blocks", "wait 400"]),  # Lines on without its block: the view shows one
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
        ("rig-orbit-armed", s, ["rail camera", "click Orbit"]),                # waiting for the click on what to circle
        ("rig-selected", s, ["rail camera", "wait 300", "click Crane"]),                   # the camera on a new crane: its settings
        ("type-flyout", s, ["rail type"]),
        ("import-menu", s, ["rail import"]),                                    # Import (Ctrl+I): a file per format, Asset library
        ("import-drop-hover", s, ["import-hover 420 300"]),                     # a file from Explorer over the viewport: its ring
        ("import-unit-note", [], toy_import("import-note import_1", "settled")),     # rescaled from centimetres: Keep original size
        ("import-part-selected", [], toy_import("select import_1.Head", "settled")),  # a part: its Material and Visible
        # Copies and scatter (brief 24): the copies item's rows (Count first, the grey line under it), right-click on a shape
        # (Make copies ›), on a surface with something selected (Scatter), on a copies item (Change near ›), a change near added
        ("copies-selected", buds(), ["select buds", "settled"]),
        ("copies-scattered", buds("surface"), ["select buds", "settled"]),
        ("copies-more", buds(), ["select buds", "more"]),
        ("copies-context-shape", s, ["context block"]),                                   # Make copies in the right-click
        ("copies-context-copies", buds(), ["context buds"]),                               # Change near
        ("copies-scatter-menu", s, ["select vase", "context block"]),                      # Scatter 'vase' on 'block'
        ("copies-near-added", buds(), ["select buds", "action copies:near:scale", "settled"]),
        ("copies-effector-selected", buds(), ["select buds", "action copies:near:turn", "select effector_1", "settled"]),
        # Simulate (brief 25; sim_qt.py, SimRow.qml): the row under the timeline in each state (never a simulation), the
        # Scene panel's Simulation group, the render sheet's line, right-click › Simulate, the rail's flyout, a body's settings
        ("sim-not-computed", drop(), ["deselect", "sim-demo not computed", "settled"]),
        ("sim-filling", drop(), ["deselect", "sim-demo running", "settled"]),
        ("sim-stored", drop(), ["deselect", "sim-demo stored", "settled"]),
        ("sim-out-of-date", drop(), ["deselect", "sim-demo out of date", "settled"]),
        ("sim-failed", drop(), ["deselect", "sim-demo failed", "settled"]),
        ("sim-stylize", drop(), ["deselect", "sim-demo stored", "settled"]),     # 26a: Timing, Simplify, Turn into keys
        ("sim-render-sheet", drop(), ["sim-demo out of date", "estimate-recorded", "render-sheet"]),
        ("sim-context", drop(), ["context buds"]),
        ("sim-flyout", drop(), ["select set", "rail simulate"]),
        ("sim-body-selected", drop(), ["select buds", "settled"]),
        ("text-typing", s, ["arm mesh:text", "mouseclick 634 500", "wait 1500", "type AURORA", "wait 600"]),
        ("drawings-list", s, ["drawings"]),
        ("bevel-too-big", s, ["arm mesh:text", "mouseclick 634 500", "wait 1500", "typeend", "set bevel 0.01", "wait 2500"]),
        ("materials-menu", s, ["materials"]),
        ("shots-menu", s, ["shots"]),
        ("shots-two", two_shots(), ["mode free", "orbit 30 5", "shots"]),       # Hero 01 ✓, Close 02, New shot from this view
        ("shot-switched", two_shots(), ["showshot close"]),
        ("shot-only-light", two_shots(), ["select key", "shotonly on", "set intensity 9"]),   # Changes: Only Hero 01, a This shot row
        ("shot-only-tag", two_shots(), ["select key", "shotonly on", "set intensity 9", "shotonly off"]),   # the tag on All shots
        ("collections-row", s, ["selectmany block vase", "action collection:new"]),       # the scene list's Collections chips
        # animation layers (layers3d.py, the kit's AnimLayers.qml): the ⧉ popover empty, then two layers, the top one chosen
        ("anim-layers-empty", s, ["page animate", "clickon animLayersButton", "wait 300"]),
        ("anim-layers-two", s, ["page animate", "select block", "clickon animLayersButton", "wait 300", "click + New layer",
                                "click + New layer", "wait 300"]),
        ("anim-layers-chosen", s, ["page animate", "select block", "clickon animLayersButton", "click + New layer",
                                   "press Escape", "wait 300"]),
        ("shot-from-view", s, ["mode free", "orbit 40 10", "shot-from-view"]),
        # Make this the shot (header, free view only; its place held in the shot camera) and its hover: the frame it takes
        ("take-view-hover", s, ["mode free", "orbit 40 10", "wait 300", "hover takeShot", "wait 700"]),
        ("shots-frame", s, ["select block", "shots"]),        # the crumb's list with Frame the selection
        ("focus-picking", s, ["select cam", "set dof true", "action focus:point"]),
        ("focus-on-item", s, ["select cam", "set dof true", "set focusItem \"vase\""]),
        ("lens-menu", s, ["select cam", "click Lenses"]),
        ("context-item", s, ["context block"]),
        ("context-empty", s, ["context -"]),
        ("view-menu", s, ["select key", "view"]),
        ("page-animate", s, ["select cam", "page animate"]),
        ("animate-stretch", lid_turn(), ["page animate", "stretch lid.rx.k800"]),       # the lid's Turn: the animation panel
        ("animate-stretch-out", lid_turn(), ["page animate", "stretch lid.rx.k800", "ease out"]),
        ("animate-poses", lid_turn(), ["page animate", "select lid", "pose Lid half open, before the buds come out of the case",
                                       "panel poses"]),
        ("animate-poses-onion", lid_turn(), ["page animate", "select lid", "frame 30", "pose Lid open", "onion on",
                                             "panel poses", "panel onion"]),                  # both panels open side by side
        ("animate-key-ease", lid_turn(), ["page animate", "select lid", "keys-menu lid.rx.k1600"]),   # a key's right-click Ease list
        ("animate-curves", lid_turn(), ["page animate", "curves on"]),              # Curves, nothing picked: every item's
        ("animate-curves-picked", lid_turn(), ["page animate", "select lid", "curves on"]),   # the lid's, Picked | All curves
        ("animate-curves-all", lid_turn(), ["page animate", "select lid", "curves on", "curves all"]),
        ("animate-onion", lid_turn(), ["page animate", "select lid", "frame 30", "onion on", "panel onion"]),
        ("page-render", s, ["deselect", "estimate-recorded", "page render"]),          # the Render page, its queue empty
        ("render-queue-two", two_shots(), ["deselect", "estimate-recorded", "page render", "queue demo"]),   # running, waiting, ended rows
        ("render-queue-finished", two_shots(), ["deselect", "estimate-recorded", "page render", "queue demo", "queue show 3"]),
        ("file-menu", s, ["file-menu"]),
        ("start-screen", s, ["startscreen open"]),
        ("export-sheet", s, ["export-open"]),
        ("render-sheet", s, ["estimate-recorded", "render-sheet"]),
        ("render-sheet-shot", s, ["page animate", "estimate-recorded", "render-sheet", "estimate-wait"]),
        ("render-sheet-exr", s, ["page animate", "estimate-recorded", "render-sheet", "estimate-wait", "sheet-format both"]),
        ("render-sheet-budget", s, ["page animate", "estimate-recorded", "render-sheet", "estimate-wait", "budget 1 s"]),
        ("commands", s, ["commands"]),
        ("commands-search", s, ["commands light"]),
        ("guides-list", s, ["guides open"]),
        ("guide", s, ["guides open agents.md"]),
        ("key-list", s, ["keylist open"]),
        ("panels-folded", s, ["panels fold"]),
        ("mesh-edit-offer", s, ["select block", "mesh-tab", "wait 300"]),
        ("mesh-edit-faces", s, ["select block", "mesh-tab", "mesh-edit", "mesh-pick top", "mesh-action extrude", "wait 600"]),
        ("mesh-edit-inset", s, ["select block", "mesh-tab", "mesh-edit", "mesh-pick top", "mesh-action inset", "wait 600"]),
        ("mesh-edit-points", s, ["select block", "mesh-tab", "mesh-edit", "mesh-kind points", "mesh-box 0.3 0.3 0.7 0.7", "wait 600"]),
        ("mesh-edit-bevel", s, ["add mesh:box", "mesh-tab", "mesh-edit", "mesh-kind edges", "mesh-box 0.2 0.2 0.8 0.8",
                                "mesh-action bevel", "wait 600"]),
        ("mesh-edit-loopcut", s, ["add mesh:box", "mesh-tab", "mesh-edit", "mesh-kind edges", "mesh-box 0.3 0.3 0.7 0.7",
                                  "mesh-action loopcut", "wait 600"]),
        ("mesh-edit-material", s, ["add mesh:box", "mesh-tab", "mesh-edit", "mesh-pick top", "wait 300"]),
        ("mesh-edit-knife", s, ["add mesh:box", "mesh-tab", "mesh-edit", "mesh-knife", "mesh-knife-at 0.42 0.45",
                                "mesh-knife-at 0.6 0.5", "wait 400"]),
        ("mesh-edit-xray", s, ["add mesh:box", "mesh-tab", "mesh-edit", "mesh-xray", "mesh-kind points",
                               "mesh-box 0.3 0.3 0.7 0.7", "wait 600"]),
        ("paint-mode", s, ["select block", "paint-b", "wait 1500"]),                    # Brush, Paint layers (none yet)
        ("paint-layers", s, ["select block", "paint-b", "wait 1500", "paint-layer", "paint-channel roughness",
                             "paint-drag 0.42 0.5 0.58 0.55", "wait 1500"]),            # a roughness stroke, its layer
        # brief 21: From the view (a drag kept as drawn, laid on what it crosses) with the coverage tint on and its line
        ("paint-view-coverage", s, ["select block", "paint-b", "wait 1500", "paint-where view", "paint-tint",
                                    "paint-drag 0.35 0.5 0.65 0.5", "wait 2500"]),
        # Clay (Q, clay_tool_qt.py): Make only, nothing to sculpt yet; then a real Lump click on the ground makes a clay
        # (clay.add: the core's clay must be built), its Brush tiles and rows; then Carve picked by a real click
        # (`settled` before and after Q: Q's action runs a frame later, and a click in the same instant met Select; after the click: the picture
        # with the new clay in it, not the one before — CL1b's "clay on the box not drawn" was that picture).
        # CL2: the Brush group is seven tiles (the six that shape in two rows, Mask on its own row) over Size and
        # Strength (3d-v4: then Steps, then the More fold with Falloff, Spacing, Front faces only, Mirror): clay-brush
        # with Carve chosen, clay-mask with Mask, the lone tile of the last row chosen (its blue must not touch the rows
        # under it at 720 high); clay-brush-more with the More fold opened by a real click, so its four rows are checked
        ("clay-tool", s, ["settled", "press Q"]),
        ("clay-made", s, ["settled", "press Q", "settled", "mouseclick 640 560", "settled"]),
        ("clay-brush", s, ["settled", "press Q", "settled", "mouseclick 640 560", "settled", "wait 300", "click Carve", "settled"]),
        ("clay-mask", s, ["settled", "press Q", "settled", "mouseclick 640 560", "settled", "wait 300", "click Mask", "settled"]),
        ("clay-brush-more", s, ["settled", "press Q", "settled", "mouseclick 640 560", "settled", "wait 300", "click More", "settled"]),
        # CL3: a drawn clay (Puff on top until the next stroke; 3d-v4: the Steps list under Size and Strength, above the
        # More fold, in sight at 900 high), and Turn into clay on the Make tiles while an exact part is selected
        ("clay-drawn", drawn_clay(), ["select buddy", "settled", "press Q", "settled"]),
        # PR4: the drawn clay with a sculpt layer made by a real click on the Steps head's "+ Layer": the Layers list
        # (Base, Layer 1 chosen, its Amount row and Layer ▾ under it) above Steps
        ("clay-layers", drawn_clay(), ["select buddy", "settled", "press Q", "settled", "clickon clayLayerAdd", "settled"]),
        # Pose (Shift+P, pose_qt.py): its joints found on the drawn clay, the bones, the panel's three rows; the right-click menu
        ("pose-tool", drawn_clay(), ["select buddy", "settled", "press Shift+P", "wait 2000", "settled"]),
        ("pose-context", drawn_clay(), ["select buddy", "settled", "press Shift+P", "wait 2000", "settled", "context buddy"]),
        ("clay-selected", drawn_clay(), ["select buddy", "settled"]),   # a clay with Select on: Material ▾ with Base colour's square under it
        ("clay-turn-into", s, ["select block", "settled", "press Q", "settled"]),
        ("long-name-paint", long_names(), [f"select {LONG_NAME}", "paint-b", "wait 1500", "paint-layer"]),
        ("long-name", long_names(), [f"select {LONG_NAME}"]),
        ("long-name-light", long_names(), [f"select {LONG_NAME}_key"]),
        ("long-status", s, [f"say {LONG_STATUS}"]),
        ("render-running", s, ["render-demo running"]),       # the header's Render while it runs: the clock against the time it said, ×
        ("render-done", s, ["render-demo done"]),             # its picture over the viewport, Show in folder
        ("render-failed-line", s, ["say Error: render: the picture was not written"]),
    ]
