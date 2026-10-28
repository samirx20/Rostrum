"""look_frame, look_sheet, look_at: the agent's eyes, through the shot's camera and the same engine as export (preview ≡ export)."""
from __future__ import annotations

import tempfile
from pathlib import Path

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools, sheet
from rostrum_core.mcp.files import look_path

from rostrum3d import through as thru
from rostrum3d.faults import note as fault_words, shot_faults
from rostrum3d.sim.fall_view import fall_note

from . import draw, onion_look, paint_canvas, picture_facts, step_look, text_facts
from .shape_look import length
from .shot import ITEM_SHOT, LOOK, TIME, check_frame, doc_and_shot, frame_of, look_renderer, seconds, size_of

tools = Tools()
LOOK_SAMPLES = 64                         # Cycles samples for a look (denoised); render_still has its own


def _settings(renderer: str) -> dict:
    return {"samples": LOOK_SAMPLES, "denoise": True} if renderer == "cycles" else {}


THROUGH = {"through": {"type": "string", "description": "A light's id (rect, disk, strip, sphere, distant): look from where it stands along "
                                                         "the way it shines (60° tall view, level) instead of through the shot camera, to aim it."}}


def _through(ctx, scene: dict, light: str, frame: int, aspect: float) -> str:
    """Add a camera standing where `light` looks from; its id."""
    try:
        cam = thru.as_camera(scene, light, frame, aspect)
    except ValueError as e:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f'through "{light}"', str(e)) from None
    if any(n["id"] == cam["id"] for n in scene["items"]):
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, "through", f'an item is already called "{cam["id"]}"; rename it')
    scene["items"].append(cam)
    return cam["id"]


@tools.tool("look_frame", {"properties": {**ITEM_SHOT, **TIME, **LOOK, **THROUGH, **onion_look.ONION, **step_look.HIGHLIGHT}})
def look_frame(ctx, args):
    """One rendered frame of a shot, seen through the SHOT's camera by the same render path as export: a PNG file and an image you
    can see. quality fast = Storm, final = Cycles (slower); renderer picks one by name (storm, cycles, stylized); neither on a shot
    whose Quality is Stylized = stylized. stylized = the
    stylized look: the only one that draws materials' Lines and Halftone (Light to colour shows in final too). through = a light's
    id: see from the light instead (what it shines on is the middle of the picture). The reply says how much of the picture is clipped
    (blown out; stylized: pure white, its picked colours are shown as they are), which lighting settings only Final applies (spread, light linking), so a quick look's missing effects are known, and
    for every text in the picture which way it reads from this camera (left to right, mirrored, upside down, seen from behind or
    edge-on, its angle to the horizontal; data `text`).
    onion = {item, mode keys|frames}: the item's onion-skin ghosts (red before, green after) as the viewport draws them, to check an arc
    or a spacing; a quick look only (not final), drawn by the live view, so no studio light or outline. highlight = "steps:arm" or
    "steps:arm,foot": outline (2 px, tinted, one colour each, labelled) what those clay steps made, by name or id (look_at's `step`
    names them); the reply gives each region's box in pixels and what hides part of it. A posed clay is outlined as posed. At this frame it also names, only when one exists, a part separated from the figure it was joined to, a thing floating above what is under it (cm), a subject cut by the frame edge (which edge); data `faults`."""
    doc, info = doc_and_shot(ctx, args)
    frame, renderer = frame_of(ctx, info, args), look_renderer(args, doc, [info])
    w, h = size_of(info, args)
    scene, engine = draw.scene_of(doc, info["id"]), draw.engine_of(ctx)
    if args.get("through"):
        scene = {**scene, "items": list(scene["items"])}       # the document's compiled scene stays as it was
        info = {**info, "camera": _through(ctx, scene, args["through"], frame, w / h)}
    wanted = step_look.chosen(ctx, doc, args["highlight"]) if args.get("highlight") else None
    ghosts = onion_look.ghosts_of(ctx, doc, info, frame, args["onion"], renderer) if args.get("onion") else None
    dest = look_path(f'{doc.item_id or "doc"}_{info["id"]}_f{frame}_{renderer}' + ("_onion" if args.get("onion") else ""), project=doc.folder)

    def job_fn(job):
        what = f"frame {frame} of {info['id']}"
        if args.get("onion"):
            out = {"frames": [{"ms": onion_look.view_png(ctx.tool, what, engine, scene, dest, ghosts, camera=info["camera"], renderer=renderer,
                                                         frame=frame, width=w, height=h).get("ms", 0)}]}
        else:
            out = draw.render(ctx.tool, what, engine, scene, camera=info["camera"], renderer=renderer, frame=frame,
                              width=w, height=h, png=str(dest), **_settings(renderer))
        t = seconds(info, frame)
        said, facts = picture_facts.line(dest, scene, renderer)
        more, more_facts = picture_facts.copies_line(getattr(engine, "copies", {}), picture_facts.item_names(doc.data.get("items", [])))
        said, facts = said + more, {**facts, **more_facts}
        if not args.get("through"):                    # a light's view has no shot camera to read the text through
            words, text = text_facts.sentence(text_facts.seen_texts(doc, info, frame, w / h))
            said, facts = said + words, {**facts, **text}
        lit, marks = _highlight(ctx, doc, info, frame, w, h, wanted, dest, engine, scene) if wanted else ("", {})
        if not args.get("through"):                    # parts apart, floating, cut by the frame edge at this frame
            faults = shot_faults(doc.data, info["id"], ctx.app.folder, at=frame)
            said, facts = said + fault_words(faults), {**facts, "faults": faults}
        return Reply(f'Frame {frame} ({t:.3f} s) of {info["id"]} through camera {info["camera"]}, {w}×{h}, {renderer}, {out["frames"][0]["ms"]:.0f} ms.{said}{lit}',
                     {**marks, "time": t, "frame": frame, "width": w, "height": h, "renderer": out.get("renderer", renderer), "camera": info["camera"],
                      **({"ghosts": [g["frame"] for g in ghosts]} if ghosts is not None else {}), "timing": out.get("timing", {}), "vram": out.get("vram", {}), **facts}, [dest], [dest], engine.take_notices())

    return ctx.long(f'look_frame {info["id"]} f{frame}', job_fn)


def _highlight(ctx, doc, info, frame, w, h, wanted, dest, engine, scene):
    """Outline the wanted clay steps on the picture at `dest`; (a sentence, {"highlight": [...]})."""
    regions = step_look.masks(doc, ctx.app.folder, info, frame, w, h, wanted)
    names = {k: step_look.SF.label(next(s for s in doc.item(k[0])["steps"] if s["id"] == k[1])) for k in regions}
    marks = step_look.overlay(dest, regions, names)
    pick = lambda x, y: draw.call(ctx.tool, f"point ({x:g}, {y:g})", engine, scene, "pick", camera=info["camera"],  # noqa: E731
                                  frame=frame, width=w, height=h, x=x, y=y)
    said = []
    for m in marks:
        m["hiddenBy"] = step_look.hidden_by(pick, m, m["clay"]) if m["pixels"] else []
        del m["mask"]
        said.append(f'{m["name"]} in {m["colour"]}: ' + (f'x {m["box"][0]}–{m["box"][2]}, y {m["box"][1]}–{m["box"][3]}'
                                                         + (f', partly behind {", ".join(m["hiddenBy"])}' if m["hiddenBy"] else "")
                                                         if m["box"] else "not seen from here"))
    return " Outlined: " + "; ".join(said) + ".", {"highlight": marks}


@tools.tool("look_sheet", {"properties": {**ITEM_SHOT, **LOOK, "start": {"type": "number", "minimum": 0, "description": "Seconds from the start of the shot. Default 0."},
                                           "end": {"type": "number", "minimum": 0, "description": "Seconds from the start of the shot. Default: the last frame."},
                                           "count": {"type": "integer", "minimum": 2, "maximum": 24, "default": 6, "description": "Frames in the sheet, evenly spaced."},
                                           "cols": {"type": "integer", "minimum": 1, "maximum": 8, "description": "Tiles per row. Default 3."},
                                           "width": {"type": "integer", "minimum": 64, "maximum": 1280, "default": 480, "description": "Width of each tile in px."}}})
def look_sheet(ctx, args):
    """A contact sheet: `count` frames spread over the shot (or a range) in one image, each tile labelled with its frame and time. Drawn fast
    (Storm; stylized for a shot whose Quality is Stylized) unless you say otherwise. Use it to check a whole move at a glance; look_frame for detail. When the shot simulates a fall or cloth, the reply also says in plain words when the range opens mid-drop or after the landing and when the last stretch doesn't move, with the fix. Also, only when one exists, names faults a client would see (worst first, a few at most, from the document on about ten frames, nothing extra rendered): a part that separates from the figure it was joined to, a thing that floats above what is under it while holding its height (cm), a main subject cut by the frame edge or leaving the frame (which edge, from when), as warnings."""
    doc, info = doc_and_shot(ctx, args)
    fps, first, last = info["fps"], info["start"], info["end"]
    f0 = first + round(args.get("start", 0.0) * fps)
    f1 = last if "end" not in args else first + round(args["end"] * fps)
    if f0 >= f1:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f"range {f0}–{f1}", f"must run forward inside the shot (frames {first}–{last})")
    check_frame(ctx, info, f0), check_frame(ctx, info, f1)
    count = args.get("count", 6)
    frames = sorted({round(f0 + (f1 - f0) * i / (count - 1)) for i in range(count)})
    renderer, tile_w = look_renderer(args, doc, [info]), args.get("width", 480)
    w, h = size_of(info, {"width": tile_w})
    cols = args.get("cols", min(3, len(frames)))
    scene, engine = draw.scene_of(doc, info["id"]), draw.engine_of(ctx)
    dest = look_path(f'{doc.item_id or "doc"}_{info["id"]}_sheet_{renderer}', project=doc.folder)

    def job_fn(job):
        with tempfile.TemporaryDirectory(prefix="rostrum3d_sheet_") as tmp:
            pngs = []
            for i, f in enumerate(frames):                # one request per frame: the contract's `frames` is a contiguous range
                png = Path(tmp) / f"f{f}.png"
                draw.render(ctx.tool, f"frame {f} of {info['id']}", engine, scene, camera=info["camera"], renderer=renderer, frame=f,
                            width=w, height=h, png=str(png), **_settings(renderer))
                pngs.append(png)
                job.progress(i + 1, len(frames))
            sw, sh = sheet.contact_sheet([(p, f"f{f}   {seconds(info, f):.2f} s") for p, f in zip(pngs, frames)], tile_w, cols, dest)
        return Reply(f'Contact sheet of {info["id"]}: {len(frames)} frames, {frames[0]}–{frames[-1]} ({seconds(info, frames[0]):.2f}–{seconds(info, frames[-1]):.2f} s), '
                     f'{renderer}, {sw}×{sh}.', {"frames": frames, "times": [round(seconds(info, f), 4) for f in frames], "width": sw, "height": sh,
                                                 "cols": cols, "camera": info["camera"]}, [dest], [dest],
                     [*engine.take_notices(), *filter(None, [fall_note(doc.data, info["id"], ctx.app.folder, (f0, f1))]),
                      *shot_faults(doc.data, info["id"], ctx.app.folder, (f0, f1))])

    return ctx.long(f'look_sheet {info["id"]}', job_fn)


def _painted_words(p: dict | None) -> str:
    return (f', painted {p["colour"]} at {p["alpha"] * 100:.0f} % by layer {p["name"]} ({p["channelLabel"]})' if p else "")


@tools.tool("look_at", {"properties": {**ITEM_SHOT, **TIME, "x": {"type": "number", "minimum": 0, "description": "Pixels from the left of the picture."},
                                        "y": {"type": "number", "minimum": 0, "description": "Pixels from the top of the picture."},
                                        "points": {"type": "array", "minItems": 1, "maxItems": 64, "items": {"type": "array", "items": {"type": "number", "minimum": 0}, "minItems": 2, "maxItems": 2},
                                                   "description": "Several points as [[x, y], …] (instead of x and y), up to 64 in one call."},
                                        "width": {"type": "integer", "minimum": 64, "maximum": 4096, "default": 960, "description": "Width of the picture the pixels count in (the one look_frame gave). Default 960."},
                                        "height": {"type": "integer", "minimum": 1, "maximum": 4096, "description": "Height of that picture. Default: follows the shot's shape."}}})
def look_at(ctx, args):
    """What is at a pixel (x, y) of a picture from the shot camera at a frame: the item id, the part (prim), its material, the point in the
    world (metres), the distance from the camera and `normal`, the surface direction there (world, unit length: "facing [0, 1, 0]" is a
    top); on a mesh with face materials `faceSet`, that face's own material; on a mesh also `uv`, the spot on its unfolded surface (paint canvas pixel
    x = u × paintSize, y = (1 − v) × paintSize; guide `painting`; look_where is the reverse) and, where it is painted, `painted`
    {layer, name, channel, colour, alpha}: the topmost shown paint layer with paint there; on a clay `local` and `localNormal`, the point and the surface's
    normal in the clay's own space (a clay paint stroke's `anchors`: [x, y, z, nx, ny, nz, pressure]; guide `painting`); on a posed
    clay also `rest`, the same spot on its rest shape: anchor paint there, as the screen does. On a clay also `step`, the step that made
    the surface there ({id, name, kind, label "arm, drawn"}; a mirrored step counts on both sides) and, once its joints are found,
    `joint` ({joint "elbow.R"-style name, distance in metres to that bone}): name parts by them in clay.step.set, look_frame
    highlight="steps:<name>" and pose.drag. Counted from the top-left of a width×height picture, the same whatever
    renderer drew it. `view` in the reply: this picture's camera as stroke.add's From the view fields (viewEye, viewTarget,
    viewFov, viewSize, viewFrame, viewShot): add `viewPoints` [[x, y, pressure], …] in this picture's px to paint from the view."""
    doc, info = doc_and_shot(ctx, args)
    points = args.get("points") or ([[args["x"], args["y"]]] if "x" in args and "y" in args else None)
    if not points or ("points" in args and ("x" in args or "y" in args)):
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, '"x", "y" and "points"', "need either x and y, or points", ["x and y", "points"])
    frame = frame_of(ctx, info, args)
    w, h = size_of(info, args, 960)
    h = args.get("height", h)
    scene, engine = draw.scene_of(doc, info["id"]), draw.engine_of(ctx)

    def job_fn(job):
        rows, kept = [], {}
        for x, y in points:                                # the engine's `point` is the world point; the pixel is kept as `pixel`
            r = draw.call(ctx.tool, f"point ({x:g}, {y:g})", engine, scene, "pick", camera=info["camera"], frame=frame, width=w, height=h, x=x, y=y)
            rows.append({"pixel": [x, y], **{k: v for k, v in r.items() if k not in ("ok", "ms")}, **step_look.about(doc, ctx.app.folder, r),
                         **paint_canvas.about(ctx, doc, scene, r, kept)})
        lines = [f'({r["pixel"][0]:g}, {r["pixel"][1]:g}): ' + (f'{r["item"]} ({r["prim"]}), material {r.get("material") or "none"}, '
                                                              f'{r["distance"]:.3g} m away at {[round(c, 3) for c in r["point"]]}'
                                                              + (f', facing {[round(c, 2) for c in r["normal"]]}' if r.get("normal") else "")
                                                              + (f', face set {r["faceSet"] or "(its own material)"}' if "faceSet" in r else "")
                                                              + (f', uv {[round(c, 4) for c in r["uv"]]}' if r.get("uv") else "")
                                                              + _painted_words(r.get("painted"))
                                                              + (f', local {[round(c, 5) for c in r["local"]]} normal '
                                                                 f'{[round(c, 3) for c in r.get("localNormal") or []]}' if r.get("local") else "")
                                                              + (f', rest {[round(c, 5) for c in r["rest"]]}' if r.get("rest") else "")
                                                              + step_look.words(r, length)
                                                              if r.get("hit") else "nothing (background)") for r in rows]
        t = seconds(info, frame)
        view = paint_canvas.shot_view(doc, info, frame, w, h)
        return Reply(f'At frame {frame} ({t:.3f} s) of {info["id"]}, picture {w}×{h}: ' + "; ".join(lines) + ".",
                     {"time": t, "frame": frame, "width": w, "height": h, "hits": rows, "view": view}, warnings=engine.take_notices())

    return ctx.long(f'look_at {info["id"]} f{frame}', job_fn)

