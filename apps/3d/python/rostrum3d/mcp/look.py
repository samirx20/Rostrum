"""look_frame, look_sheet, look_at: the agent's eyes, through the shot's camera and the same engine as export (preview ≡ export)."""
from __future__ import annotations

import tempfile
from pathlib import Path

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools, sheet
from rostrum_core.mcp.faults import NOTES, asked
from rostrum_core.mcp.files import look_path

from rostrum3d import through as thru, view_look
from rostrum3d.resolve import Frames
from rostrum3d.sim.fall_view import fall_note

from . import draw, onion_look, paint_canvas, picture_facts, shot_faults, step_look, text_facts
from .shape_look import length
from .shot import COUNT, ITEM_SHOT, LOOK, TIME, WIDTH, count_of, width_of, check_frame, doc_and_shot, frame_of, look_renderer, quality_line, seconds, size_of

tools = Tools()
LOOK_SAMPLES = 64                         # Cycles samples for a look (denoised); render_still has its own


def _settings(renderer: str) -> dict:
    return {"samples": LOOK_SAMPLES, "denoise": True} if renderer == "cycles" else {}


THROUGH = {"through": {"type": "string", "description": "A light's id: look from the light the way it shines, to aim it."}}
VIEW = {"view": {"type": "object", "description": "Look from here, without moving the shot camera or changing the document: "
                 '{"from": [x, y, z], "to": [x, y, z] or a part} or {"around": a part, "turn_deg": walk round it to the camera\'s '
                 'right, "tilt_deg": from higher up, "distance": m (default the camera\'s)}; "lens_mm" (default the shot camera\'s). '
                 'A part: an item id or a clay joint "buddy.hand.L".',
                 "properties": {"from": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                                "to": {"type": ["array", "string"], "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                                "around": {"type": "string"}, "turn_deg": {"type": "number"}, "tilt_deg": {"type": "number"},
                                "distance": {"type": "number", "exclusiveMinimum": 0}, "lens_mm": {"type": "number", "exclusiveMinimum": 0}},
                 "additionalProperties": False}}


def view_of(ctx, doc, info: dict, spec: dict, frame: int) -> dict:
    """The view (view_look.place) at `frame`, read from the document; a view that can't stand is a BAD_ARGUMENT."""
    try:
        return view_look.place(Frames(doc.data, range(info["start"], frame + 1), info["fps"], ctx.app.folder), info["camera"], spec, frame)
    except ValueError as e:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, "view", str(e)) from None


def _add_camera(ctx, scene: dict, cam: dict) -> str:
    if any(n["id"] == cam["id"] for n in scene["items"]):
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, "view", f'an item is already called "{cam["id"]}"; rename it')
    scene["items"].append(cam)
    return cam["id"]


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


@tools.tool("look_frame", {"properties": {**ITEM_SHOT, **TIME, **LOOK, **NOTES, **THROUGH, **VIEW, **onion_look.ONION, **step_look.HIGHLIGHT}})
def look_frame(ctx, args):
    """One frame (`through` a light, `view` from anywhere, `onion` ghosts, `highlight` clay steps); says what is clipped, how texts read."""
    doc, info = doc_and_shot(ctx, args)
    frame, renderer = frame_of(ctx, info, args), look_renderer(args, doc, [info])
    w, h = size_of(info, args)
    scene, engine = draw.scene_of(doc, info["id"]), draw.engine_of(ctx)
    if args.get("through") and args.get("view"):
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, '"through" and "view"', "were both given", ["through", "view"], "Give one.")
    away = bool(args.get("through") or args.get("view"))      # not the shot camera's picture
    view = view_of(ctx, doc, info, args["view"], frame) if args.get("view") else None
    if away:
        scene = {**scene, "items": list(scene["items"])}       # the document's compiled scene stays as it was
        info = {**info, "camera": _through(ctx, scene, args["through"], frame, w / h) if args.get("through")
                else _add_camera(ctx, scene, view_look.as_camera(view))}
    wanted = step_look.chosen(ctx, doc, args["highlight"]) if args.get("highlight") else None
    ghosts = onion_look.ghosts_of(ctx, doc, info, frame, args["onion"], renderer) if args.get("onion") else None
    dest = look_path(f'{doc.item_id or "doc"}_{info["id"]}_f{frame}_{renderer}' + ("_onion" if args.get("onion") else "") + ("_view" if view else ""), project=doc.folder)

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
        miss, miss_facts = picture_facts.storm_misses(doc.data, renderer)
        said, facts = said + miss, {**facts, **miss_facts}
        if not away:                                   # a light's view or a view has no shot camera to read the text through
            words, text = text_facts.sentence(text_facts.seen_texts(doc, info, frame, w / h))
            said, facts = said + words, {**facts, **text}
        lit, marks = _highlight(ctx, doc, info, frame, w, h, wanted, dest, engine, scene) if wanted else ("", {})
        found = None if away or not asked(args) else shot_faults.check(doc.data, info, [frame], {frame: dest}, ctx.app.folder, renderer)   # a light's view is not the shot's picture
        seat = f'from a view {view_look.words(view)} (the shot camera and document unchanged)' if view else f'through camera {info["camera"]}'
        return Reply(f'Frame {frame} ({t:.3f} s) of {info["id"]} {seat}, {w}×{h}, {renderer}, {out["frames"][0]["ms"]:.0f} ms.{said}{lit}{quality_line(renderer)}',
                     {**marks, "time": t, "frame": frame, "width": w, "height": h, "renderer": out.get("renderer", renderer), "camera": info["camera"],
                      **({"view": {k: [round(c, 4) for c in view[k]] if k in ("eye", "target") else round(view[k], 3) for k in view}} if view else {}),
                      **({"ghosts": [g["frame"] for g in ghosts]} if ghosts is not None else {}), "timing": out.get("timing", {}), "vram": out.get("vram", {}), **facts},
                     [dest], [dest], engine.take_notices(), faults=found)

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


@tools.tool("look_sheet", {"properties": {**ITEM_SHOT, **LOOK, **NOTES, "start": {"type": "number", "minimum": 0, "description": "Seconds from the shot's start. Default 0."},
                                           "end": {"type": "number", "minimum": 0, "description": "Seconds from the shot's start. Default: its last frame."},
                                           **COUNT,
                                           "cols": {"type": "integer", "minimum": 1, "maximum": 8, "description": "Tiles per row. Default 3."},
                                           **WIDTH}})
def look_sheet(ctx, args):
    """`count` frames over the shot or `start`–`end`: check a whole move."""
    doc, info = doc_and_shot(ctx, args)
    fps, first, last = info["fps"], info["start"], info["end"]
    f0 = first + round(args.get("start", 0.0) * fps)
    f1 = last if "end" not in args else first + round(args["end"] * fps)
    if f0 >= f1:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f"range {f0}–{f1}", f"must run forward inside the shot (frames {first}–{last})")
    check_frame(ctx, info, f0), check_frame(ctx, info, f1)
    count = count_of(ctx, args, 6, 2, 24)
    frames = sorted({round(f0 + (f1 - f0) * i / (count - 1)) for i in range(count)})
    renderer, tile_w = look_renderer(args, doc, [info]), width_of(ctx, args, 480, 1280)
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
            found = (shot_faults.check(doc.data, info, frames, dict(zip(frames, pngs)), ctx.app.folder, renderer)     # the tiles are still on disk here
                     if asked(args) else None)
        return Reply(f'Contact sheet of {info["id"]}: {len(frames)} frames, {frames[0]}–{frames[-1]} ({seconds(info, frames[0]):.2f}–{seconds(info, frames[-1]):.2f} s), '
                     f'{renderer}, {sw}×{sh}.{quality_line(renderer)}', {"frames": frames, "times": [round(seconds(info, f), 4) for f in frames], "width": sw, "height": sh,
                                                 "cols": cols, "camera": info["camera"]}, [dest], [dest],
                     [*engine.take_notices(), *filter(None, [fall_note(doc.data, info["id"], ctx.app.folder, (f0, f1)) if asked(args) else ""])], faults=found)

    return ctx.long(f'look_sheet {info["id"]}', job_fn)


def _painted_words(p: dict | None) -> str:
    return (f', painted {p["colour"]} at {p["alpha"] * 100:.0f} % by layer {p["name"]} ({p["channelLabel"]})' if p else "")


@tools.tool("look_at", {"properties": {**ITEM_SHOT, **TIME, "x": {"type": "number", "minimum": 0, "description": "Pixels from the left of the picture."},
                                        "y": {"type": "number", "minimum": 0, "description": "Pixels from the top of the picture."},
                                        "points": {"type": "array", "minItems": 1, "maxItems": 64, "items": {"type": "array", "items": {"type": "number", "minimum": 0}, "minItems": 2, "maxItems": 2},
                                                   "description": "Several points [[x, y], …] instead of x and y (up to 64)."},
                                        "width": {"type": "integer", "minimum": 64, "maximum": 4096, "default": 960, "description": "Width of the picture you were shown (x, y count in it). Default 960."},
                                        "height": {"type": "integer", "minimum": 1, "maximum": 4096, "description": "That picture's height. Default: the shot's shape."}}})
def look_at(ctx, args):
    """What is at pixel (x, y) of the picture you were shown (same `width`): the item, its part, material, world point,
    distance and surface direction; on a clay its `step` and nearest `joint`; on a painted surface `uv` and `painted`.
    Several points at once with `points`. The reverse is look_frame what "where". Guide 'agents' (The loop) and 'painting'."""
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

