"""look_material: one of the document's materials on a ball (or a plane), turned in a strip of angles under the scene's own lights."""
from __future__ import annotations

import copy
import math
import tempfile
from pathlib import Path

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools, sheet
from rostrum_core.mcp.files import look_path

from rostrum3d import aim, build, graph, ops_paint
from rostrum3d.compile import describe
from rostrum3d.material_ball import BALL_SHAPE, final_reasons

from . import draw
from .look import _settings
from .shot import ITEM_SHOT, QUALITY, RENDERERS, doc_and_shot

tools = Tools()
ELEVATION, DISTANCE, FOCAL = 20.0, 6.0, 50.0           # the camera: degrees above level, in radii from the ball, lens in mm
KEEP = ("light", "camera", "group")                    # the rest of the scene is hidden: only its lights stay


def find(ctx, doc, name: str) -> dict:
    mats = doc.data.get("materials", [])
    hit = next((m for m in mats if m["id"] == name), None) or next((m for m in mats if str(m.get("name", "")).lower() == name.lower()), None)
    if hit is None:
        raise RostrumError.not_found(ctx.tool, "material", name, [m["id"] for m in mats], "the materials of this document (id or name)")
    return hit


def renderer_for(args: dict, reasons: list[str]) -> tuple[str, str]:
    """(renderer, why): the one asked for, else Final when the material needs it, else Storm."""
    if args.get("renderer"):
        return args["renderer"], f'you asked for {args["renderer"]}'
    if args.get("quality"):
        return QUALITY[args["quality"]], f'you asked for quality {args["quality"]}'
    return ("cycles", "this material needs it: " + "; ".join(reasons)) if reasons else ("storm", "nothing in this material needs Final")


def staged(doc, info: dict, mat: dict, shape: str, radius: float, count: int) -> tuple[dict, list[str], list[float]]:
    """(the scene, camera ids, their azimuths in degrees): a copy of the document with everything but its lights hidden, the material
    on a ball or plane where the shot camera's line of sight meets the ground (else 2 m ahead), and a camera per angle around it."""
    data = copy.deepcopy(doc.data)
    stack = list(data.get("items", []))
    while stack:
        it = stack.pop()
        it["visible"] = it.get("visible", True) if it["type"] in KEEP else False
        stack += it.get("children", [])
    pose = ops_paint.shot_pose(doc.data, next(s for s in doc.data["shots"] if s["id"] == info["id"]), info["start"])
    eye = pose["eye"]
    fwd = [t - e for t, e in zip(pose["target"], eye)]
    reach = -eye[1] / fwd[1] if fwd[1] < -1e-6 else 2.0
    at = [e + reach * f for e, f in zip(eye, fwd)]
    centre = [at[0], radius if shape == "ball" else 0.01, at[2]]
    own = {"ball": {**BALL_SHAPE, "radius": radius}, "plane": {"shape": "plane", "width": 2 * radius, "depth": 2 * radius}}[shape]
    data["items"].append(build.make("mesh", "look_material_shape", {**own, "material": mat["id"], "x": centre[0], "y": centre[1], "z": centre[2]}, "look_material"))
    azimuth0 = math.degrees(math.atan2(eye[0] - at[0], eye[2] - at[2]))
    ids, azimuths = [], []
    for i in range(count):
        az = azimuth0 + 360.0 * i / count
        a, e = math.radians(az), math.radians(ELEVATION)
        pos = [centre[0] + DISTANCE * radius * math.sin(a) * math.cos(e), centre[1] + DISTANCE * radius * math.sin(e),
               centre[2] + DISTANCE * radius * math.cos(a) * math.cos(e)]
        rx, ry, rz = aim.aim_rotation(aim.IDENTITY, pos, centre)
        data["items"].append(build.make("camera", f"look_material_cam{i}", {"x": pos[0], "y": pos[1], "z": pos[2], "rx": rx, "ry": ry, "rz": rz,
                                                                            "focalLength": FOCAL}, "look_material"))
        ids.append(f"look_material_cam{i}")
        azimuths.append(round((az - azimuth0) % 360, 1))
    return describe(data, info["id"], doc.folder), ids, azimuths


@tools.tool("look_material", {"properties": {
    **ITEM_SHOT,
    "material": {"type": "string", "description": "The material's id or name."},
    "shape": {"enum": ["ball", "plane"], "default": "ball", "description": "ball = a sphere; plane = a flat square lying face up (to see a texture, grain or a brushed direction)."},
    "count": {"type": "integer", "minimum": 4, "maximum": 8, "default": 6, "description": "Angles around it, evenly spaced, the first the way the shot camera sees it."},
    "radius": {"type": "number", "exclusiveMinimum": 0, "default": 0.15, "description": "Ball radius (or half a plane's side) in metres; it sits where the shot camera's view meets the ground."},
    "tile_width": {"type": "integer", "minimum": 64, "maximum": 640, "default": 256, "description": "Width of each (square) picture in px."},
    "quality": {"enum": list(QUALITY), "description": "fast = Storm, final = Cycles. Default: Cycles when the material needs it (glass, metal, coat, Final-only settings), else Storm."},
    "renderer": {"enum": list(RENDERERS), "description": "Overrides quality."}}, "required": ["material"]})
def look_material(ctx, args):
    """One material of the document shown on a ball (or a flat square) as a small turntable: `count` angles in ONE strip, under the SCENE's
    own lights (the document's lights, its sky; everything else hidden), not a studio. Drawn with Storm unless the material needs Cycles
    (glass / transmission, metal, clear coat, Final-only settings): then Final is picked for you, and the reply says which renderer drew it
    and why (ask quality fast to force Storm). Use it to judge a material's look, how its highlight travels, before putting it on a shot.
    A material with blocks (graph.add / graph.connect) is drawn with them, and the reply lists its blocks and wires (`blocks`:
    graph.describe's blocks and wires), as bright in Storm as in Final under bulbs, spots and panels. An unknown material fails, listing the document's materials; a scene with no light fails
    (the ball would be black)."""
    doc, info = doc_and_shot(ctx, args)
    mat = find(ctx, doc, args["material"])
    lights = [it["id"] for it in _walk(doc.data.get("items", [])) if it["type"] == "light" and it.get("visible", True)]
    if not lights:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, "scene", "has no visible light, so the material would show black",
                           hint="Add a light (or a sky dome) to the document, then look again.")
    reasons = final_reasons(mat) + graph.final_only(mat)
    renderer, why = renderer_for(args, reasons)
    shape, count, tile_w, radius = args.get("shape", "ball"), args.get("count", 6), args.get("tile_width", 256), args.get("radius", 0.15)
    scene, cams, angles = staged(doc, info, mat, shape, radius, count)
    engine = draw.engine_of(ctx)
    dest = look_path(f'{doc.item_id or "doc"}_material_{mat["id"]}_{shape}_{renderer}', project=doc.folder)

    def job_fn(job):
        with tempfile.TemporaryDirectory(prefix="rostrum3d_material_") as tmp:
            tiles = []
            for i, cam in enumerate(cams):
                png = Path(tmp) / f"a{i}.png"
                draw.render(ctx.tool, f'{mat["id"]} at {angles[i]:g}°', engine, scene, camera=cam, renderer=renderer, frame=info["start"],
                            width=tile_w, height=tile_w, png=str(png), **_settings(renderer))
                tiles.append((png, f"{angles[i]:g}°" + ("  (the shot's view)" if i == 0 else "")))
                job.progress(i + 1, len(cams))
            sw, sh = sheet.contact_sheet(tiles, tile_w, len(tiles), dest)
        said = (f'Material {mat["id"]} ("{mat.get("name") or mat["id"]}") on a {shape} of {radius * 100:g} cm, {count} angles from the shot\'s view '
                f'in {360 / count:g}° steps, {ELEVATION:g}° above level, under the scene\'s lights ({", ".join(lights)}), everything else hidden. '
                f'Drawn with {"Cycles (Final)" if renderer == "cycles" else renderer.capitalize()}, {sw}×{sh}: {why}.'
                + (f" {graph.text(mat)}" if graph.has_graph(mat) else ""))
        return Reply(said, {"material": mat["id"], "shape": shape, "angles": angles, "renderer": renderer, "why": why, "needsFinal": reasons,
                            "lights": lights, "width": sw, "height": sh,
                            **({"blocks": graph.describe(mat, catalogue=False)} if graph.has_graph(mat) else {})}, [dest], [dest], engine.take_notices())

    return ctx.long(f'look_material {mat["id"]}', job_fn)


def _walk(items):
    for it in items:
        yield it
        yield from _walk(it.get("children", []))
